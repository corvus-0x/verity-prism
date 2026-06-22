import json

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.document_extraction import DocumentExtraction
from app.models.document_schema import DocumentSchema
from app.schemas.document import ExtractionCreateIn
from app.schemas.review import ExtractionCorrectionIn, ReviewQueueItem
from app.services import audit

# image_b64 can be large; 200KB is generous for a single field region.
EVIDENCE_MAX_BYTES = 204_800


class ReviewError(Exception):
    """Domain error carrying the HTTP status the router should surface.
    Keeps the service free of any FastAPI dependency."""

    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


def _get_active_document(db: Session, workspace_id: str, document_id: str) -> Document | None:
    return (
        db.query(Document)
        .filter(
            Document.id == document_id,
            Document.workspace_id == workspace_id,
            Document.is_deleted == False,  # noqa: E712
        )
        .first()
    )


def _check_evidence_size(evidence) -> None:
    if evidence and len(json.dumps(evidence).encode("utf-8")) > EVIDENCE_MAX_BYTES:
        raise ReviewError(413, "Evidence payload exceeds 200KB limit")


def _mark_complete_if_resolved(db: Session, doc: Document) -> None:
    """If no field's latest attempt is still below threshold, flip the document
    back to 'complete'. Mirrors the pipeline's needs_review gating."""
    schema = db.query(DocumentSchema).filter(DocumentSchema.id == doc.schema_id).first()
    if not schema:
        return
    latest_subq = (
        db.query(
            DocumentExtraction.field_name,
            func.max(DocumentExtraction.attempt).label("max_attempt"),
        )
        .filter(DocumentExtraction.document_id == doc.id)
        .group_by(DocumentExtraction.field_name)
        .subquery()
    )
    remaining = (
        db.query(func.count(DocumentExtraction.id))
        .join(
            latest_subq,
            (DocumentExtraction.field_name == latest_subq.c.field_name)
            & (DocumentExtraction.attempt == latest_subq.c.max_attempt),
        )
        .filter(
            DocumentExtraction.document_id == doc.id,
            DocumentExtraction.attempt < 3,
            DocumentExtraction.confidence < schema.default_confidence_threshold,
        )
        .scalar()
    )
    if remaining == 0:
        doc.extraction_status = "complete"


def get_review_queue(db: Session, workspace_id: str) -> list[ReviewQueueItem]:
    """Documents in needs_review, each with a count of fields still below threshold
    and not yet human-corrected."""
    latest_subq = (
        db.query(
            DocumentExtraction.document_id,
            DocumentExtraction.field_name,
            func.max(DocumentExtraction.attempt).label("max_attempt"),
        )
        .group_by(DocumentExtraction.document_id, DocumentExtraction.field_name)
        .subquery()
    )

    low_conf_subq = (
        db.query(
            DocumentExtraction.document_id,
            func.count(DocumentExtraction.id).label("low_count"),
        )
        .join(
            latest_subq,
            (DocumentExtraction.document_id == latest_subq.c.document_id)
            & (DocumentExtraction.field_name == latest_subq.c.field_name)
            & (DocumentExtraction.attempt == latest_subq.c.max_attempt),
        )
        .join(Document, Document.id == DocumentExtraction.document_id)
        .join(DocumentSchema, DocumentSchema.id == Document.schema_id)
        .filter(
            DocumentExtraction.attempt < 3,
            DocumentExtraction.confidence < DocumentSchema.default_confidence_threshold,
        )
        .group_by(DocumentExtraction.document_id)
        .subquery()
    )

    rows = (
        db.query(
            Document.id.label("document_id"),
            Document.workspace_id,
            Document.filename,
            Document.detected_doc_type,
            Document.uploaded_at,
            low_conf_subq.c.low_count.label("low_confidence_count"),
        )
        .join(low_conf_subq, low_conf_subq.c.document_id == Document.id)
        .filter(
            Document.workspace_id == workspace_id,
            Document.extraction_status == "needs_review",
            Document.is_deleted == False,  # noqa: E712
        )
        .all()
    )

    return [
        ReviewQueueItem(
            document_id=r.document_id,
            workspace_id=r.workspace_id,
            filename=r.filename,
            detected_doc_type=r.detected_doc_type,
            low_confidence_count=r.low_confidence_count,
            uploaded_at=r.uploaded_at,
        )
        for r in rows
    ]


def correct_extraction(
    db: Session,
    workspace_id: str,
    document_id: str,
    extraction_id: str,
    user_id: str,
    body: ExtractionCorrectionIn,
) -> DocumentExtraction:
    """Apply a human correction as a new attempt=3 row (originals preserved).
    Flips the document back to 'complete' when no field still needs review."""
    doc = _get_active_document(db, workspace_id, document_id)
    if not doc:
        raise ReviewError(404, "Document not found")

    source = (
        db.query(DocumentExtraction)
        .filter(
            DocumentExtraction.id == extraction_id,
            DocumentExtraction.document_id == document_id,
        )
        .first()
    )
    if not source:
        raise ReviewError(404, "Extraction not found")

    _check_evidence_size(body.evidence)

    before_state = {
        "field_name": source.field_name,
        "field_value": source.field_value,
        "confidence": source.confidence,
        "attempt": source.attempt,
    }

    correction = DocumentExtraction(
        document_id=document_id,
        workspace_id=workspace_id,
        field_name=source.field_name,
        field_value=body.field_value,
        field_type=source.field_type,
        confidence=1.0,
        ocr_confidence=1.0,
        schema_id=source.schema_id,
        attempt=3,
        evidence=body.evidence,
    )
    db.add(correction)
    db.flush()

    _mark_complete_if_resolved(db, doc)

    db.commit()
    db.refresh(correction)

    audit.log(
        db,
        action="extraction_corrected",
        user_id=user_id,
        workspace_id=workspace_id,
        entity_type="document",
        entity_id=document_id,
        before_state=before_state,
        after_state={
            "field_name": correction.field_name,
            "field_value": correction.field_value,
            "confidence": correction.confidence,
            "attempt": correction.attempt,
        },
    )
    return correction


def flag_document(
    db: Session,
    workspace_id: str,
    document_id: str,
    user_id: str,
    flag_reason: str,
    flag_note: str | None,
) -> Document:
    """Store a structured rejection reason on a document; does not change status."""
    doc = _get_active_document(db, workspace_id, document_id)
    if not doc:
        raise ReviewError(404, "Document not found")

    before_state = {"flag_reason": doc.flag_reason, "flag_note": doc.flag_note}
    doc.flag_reason = flag_reason
    doc.flag_note = flag_note
    db.commit()
    db.refresh(doc)

    audit.log(
        db,
        action="document_flagged",
        user_id=user_id,
        workspace_id=workspace_id,
        entity_type="document",
        entity_id=document_id,
        before_state=before_state,
        after_state={"flag_reason": doc.flag_reason, "flag_note": doc.flag_note},
    )
    return doc


def create_extraction(
    db: Session, workspace_id: str, document_id: str, user_id: str, body: ExtractionCreateIn
) -> DocumentExtraction:
    """Create an attempt=3 row for a field the pipeline never extracted.
    Validates the field against the document's schema before inserting."""
    doc = _get_active_document(db, workspace_id, document_id)
    if not doc:
        raise ReviewError(404, "Document not found")

    if doc.schema_id and body.schema_id != doc.schema_id:
        raise ReviewError(400, "schema_id does not match document schema")

    schema_for_validation = (
        db.query(DocumentSchema).filter(DocumentSchema.id == doc.schema_id).first()
    )
    if schema_for_validation:
        valid_names = {f["name"] for f in (schema_for_validation.schema_fields or [])}
        if valid_names and body.field_name not in valid_names:
            raise ReviewError(400, f"field '{body.field_name}' is not defined in schema")

    _check_evidence_size(body.evidence)

    row = DocumentExtraction(
        document_id=document_id,
        workspace_id=workspace_id,
        field_name=body.field_name,
        field_value=body.field_value,
        field_type=body.field_type,
        confidence=1.0,
        ocr_confidence=1.0,
        schema_id=body.schema_id,
        attempt=3,
        evidence=body.evidence,
    )
    db.add(row)
    db.flush()

    _mark_complete_if_resolved(db, doc)

    db.commit()
    db.refresh(row)

    audit.log(
        db,
        action="field_created",
        user_id=user_id,
        workspace_id=workspace_id,
        entity_type="document",
        entity_id=document_id,
        before_state=None,
        after_state={
            "field_name": row.field_name,
            "field_value": row.field_value,
            "evidence_type": (row.evidence or {}).get("type"),
        },
    )
    return row
