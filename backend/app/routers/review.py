import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_workspace_or_404
from app.models.document import Document
from app.models.document_extraction import DocumentExtraction
from app.models.document_schema import DocumentSchema
from app.models.user import User
from app.schemas.document import ExtractionCreateIn, ExtractionOut
from app.schemas.review import (
    ExtractionCorrectionIn,
    ExtractionCorrectionOut,
    FlagDocumentIn,
    FlagDocumentOut,
    ReviewQueueItem,
)
from app.services import audit
from app.services.auth import get_current_user

router = APIRouter(prefix="/workspaces/{workspace_id}", tags=["review"])


@router.get("/review-queue", response_model=list[ReviewQueueItem])
def get_review_queue(
    workspace_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Return documents with extraction_status='needs_review' in this workspace.
    Includes a count of fields still below threshold and not yet human-corrected.
    """
    get_workspace_or_404(workspace_id, user, db)

    # Subquery: latest attempt per field per document
    latest_subq = (
        db.query(
            DocumentExtraction.document_id,
            DocumentExtraction.field_name,
            func.max(DocumentExtraction.attempt).label("max_attempt"),
        )
        .group_by(DocumentExtraction.document_id, DocumentExtraction.field_name)
        .subquery()
    )

    # Count of fields still below threshold (latest attempt < 3 and confidence below schema threshold)
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
            Document.is_deleted == False,
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


@router.patch(
    "/documents/{document_id}/extractions/{extraction_id}/correct",
    response_model=ExtractionCorrectionOut,
)
def correct_extraction(
    workspace_id: str,
    document_id: str,
    extraction_id: str,
    body: ExtractionCorrectionIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Apply a human correction to a low-confidence field.
    Inserts a new row with attempt=3 and confidence=1.0 — the original rows are preserved.
    If all fields are now corrected, flips document status back to 'complete'.
    """
    get_workspace_or_404(workspace_id, user, db, required_roles={"owner", "analyst"}, require_active=True)

    # Verify the document belongs to this workspace
    doc = db.query(Document).filter(
        Document.id == document_id,
        Document.workspace_id == workspace_id,
        Document.is_deleted == False,
    ).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # Verify the extraction row belongs to this document
    source = db.query(DocumentExtraction).filter(
        DocumentExtraction.id == extraction_id,
        DocumentExtraction.document_id == document_id,
    ).first()
    if not source:
        raise HTTPException(status_code=404, detail="Extraction not found")

    # Guard evidence payload size — image_b64 can be large; 200KB is generous for a field region
    if body.evidence:
        if len(json.dumps(body.evidence).encode("utf-8")) > 204_800:
            raise HTTPException(status_code=413, detail="Evidence payload exceeds 200KB limit")

    before_state = {
        "field_name": source.field_name,
        "field_value": source.field_value,
        "confidence": source.confidence,
        "attempt": source.attempt,
    }

    # Insert human correction as attempt=3
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

    # Check if any fields still need review (latest attempt < 3 and below threshold)
    schema = db.query(DocumentSchema).filter(DocumentSchema.id == doc.schema_id).first()
    if schema:
        latest_subq = (
            db.query(
                DocumentExtraction.field_name,
                func.max(DocumentExtraction.attempt).label("max_attempt"),
            )
            .filter(DocumentExtraction.document_id == document_id)
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
                DocumentExtraction.document_id == document_id,
                DocumentExtraction.attempt < 3,
                DocumentExtraction.confidence < schema.default_confidence_threshold,
            )
            .scalar()
        )
        if remaining == 0:
            doc.extraction_status = "complete"

    db.commit()
    db.refresh(correction)

    audit.log(
        db,
        action="extraction_corrected",
        user_id=user.id,
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


@router.patch(
    "/documents/{document_id}/flag",
    response_model=FlagDocumentOut,
)
def flag_document(
    workspace_id: str,
    document_id: str,
    body: FlagDocumentIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Store a structured rejection reason on a document.
    Flag reason and note travel with the document through processing.
    Does not change extraction_status — use the correction endpoint to resolve fields.
    """
    get_workspace_or_404(workspace_id, user, db, required_roles={"owner", "analyst"}, require_active=True)

    doc = db.query(Document).filter(
        Document.id == document_id,
        Document.workspace_id == workspace_id,
        Document.is_deleted == False,
    ).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    before_state = {"flag_reason": doc.flag_reason, "flag_note": doc.flag_note}

    doc.flag_reason = body.flag_reason
    doc.flag_note = body.flag_note
    db.commit()
    db.refresh(doc)

    audit.log(
        db,
        action="document_flagged",
        user_id=user.id,
        workspace_id=workspace_id,
        entity_type="document",
        entity_id=document_id,
        before_state=before_state,
        after_state={"flag_reason": doc.flag_reason, "flag_note": doc.flag_note},
    )

    return doc


@router.post(
    "/documents/{document_id}/extractions",
    response_model=ExtractionOut,
    status_code=201,
)
def create_extraction(
    workspace_id: str,
    document_id: str,
    body: ExtractionCreateIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Create a new attempt=3 extraction row for a field with no prior extraction.
    Used by the review pane when an operator enters a value for a field the
    pipeline never extracted.
    """
    get_workspace_or_404(workspace_id, user, db, required_roles={"owner", "analyst"}, require_active=True)

    doc = db.query(Document).filter(
        Document.id == document_id,
        Document.workspace_id == workspace_id,
        Document.is_deleted == False,
    ).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # Validate schema_id matches doc and field_name exists in that schema
    if doc.schema_id and body.schema_id != doc.schema_id:
        raise HTTPException(status_code=400, detail="schema_id does not match document schema")
    schema_for_validation = db.query(DocumentSchema).filter(
        DocumentSchema.id == doc.schema_id
    ).first()
    if schema_for_validation:
        valid_names = {f["name"] for f in (schema_for_validation.schema_fields or [])}
        if valid_names and body.field_name not in valid_names:
            raise HTTPException(
                status_code=400,
                detail=f"field '{body.field_name}' is not defined in schema",
            )

    if body.evidence:
        if len(json.dumps(body.evidence).encode("utf-8")) > 204_800:
            raise HTTPException(status_code=413, detail="Evidence payload exceeds 200KB limit")

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

    # Flip document to complete if no fields still need review
    schema = db.query(DocumentSchema).filter(DocumentSchema.id == doc.schema_id).first()
    if schema:
        latest_subq = (
            db.query(
                DocumentExtraction.field_name,
                func.max(DocumentExtraction.attempt).label("max_attempt"),
            )
            .filter(DocumentExtraction.document_id == document_id)
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
                DocumentExtraction.document_id == document_id,
                DocumentExtraction.attempt < 3,
                DocumentExtraction.confidence < schema.default_confidence_threshold,
            )
            .scalar()
        )
        if remaining == 0:
            doc.extraction_status = "complete"

    db.commit()
    db.refresh(row)

    audit.log(
        db,
        action="field_created",
        user_id=user.id,
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
