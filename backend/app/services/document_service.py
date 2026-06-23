from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.document_extraction import DocumentExtraction
from app.models.document_schema import DocumentSchema
from app.services import audit
from app.services.extraction_engine import extract_fields, save_extractions


def list_documents(db: Session, workspace_id: str) -> list[Document]:
    """List active documents in a workspace."""
    return (
        db.query(Document)
        .filter(
            Document.workspace_id == workspace_id,
            Document.is_deleted == False,  # noqa: E712
        )
        .all()
    )


def get_document(db: Session, workspace_id: str, document_id: str) -> Document | None:
    """Fetch one active document scoped to a workspace; None if not found."""
    return (
        db.query(Document)
        .filter(
            Document.id == document_id,
            Document.workspace_id == workspace_id,
            Document.is_deleted == False,  # noqa: E712
        )
        .first()
    )


def list_extraction_history(db: Session, document_id: str) -> list[DocumentExtraction]:
    """All extraction rows for a document across attempts, ordered for display."""
    return (
        db.query(DocumentExtraction)
        .filter(DocumentExtraction.document_id == document_id)
        .order_by(DocumentExtraction.field_name, DocumentExtraction.attempt)
        .all()
    )


def list_export_documents(db: Session, workspace_id: str) -> list[Document]:
    """Active documents eligible for export (extraction complete or needs review)."""
    return (
        db.query(Document)
        .filter(
            Document.workspace_id == workspace_id,
            Document.extraction_status.in_(["complete", "needs_review"]),
            Document.is_deleted == False,  # noqa: E712
        )
        .all()
    )


def reprocess_document(document_id: str, schema_id: str, db: Session) -> Document:
    """Re-extract a document against a forced schema, skipping type detection.

    Used after a schema proposal is applied: the operator already knows which
    schema this document should use, so re-running detection (which could
    re-classify it as OTHER) is wrong. Pins schema_id + detected_doc_type,
    clears prior extractions, and re-extracts from the stored ocr_text.
    """
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise ValueError(f"Document {document_id} not found")
    schema = db.query(DocumentSchema).filter(DocumentSchema.id == schema_id).first()
    if not schema:
        raise ValueError(f"Schema {schema_id} not found")
    if not doc.ocr_text:
        raise ValueError("Document has no ocr_text — cannot reprocess without source text")

    # Clear prior extractions so the document starts clean.
    db.query(DocumentExtraction).filter(DocumentExtraction.document_id == doc.id).delete()

    # Pin the schema; do NOT run detection.
    doc.schema_id = schema.id
    doc.detected_doc_type = schema.document_type
    doc.extraction_error = None

    raw = extract_fields(doc.ocr_text, schema, doc.id, doc.workspace_id)
    save_extractions(raw, doc.id, doc.workspace_id, schema.id, db)

    if schema.parse_strategy == "claude" and schema.schema_fields and not raw:
        doc.extraction_status = "needs_review"
        doc.extraction_error = "Reprocess returned zero fields"
    else:
        doc.extraction_status = "complete"
    db.flush()

    audit.log(
        db,
        action="document_reprocessed",
        user_id=doc.uploaded_by,
        workspace_id=doc.workspace_id,
        entity_type="document",
        entity_id=doc.id,
        after_state={"schema_id": schema.id, "status": doc.extraction_status, "fields": len(raw)},
    )
    return doc
