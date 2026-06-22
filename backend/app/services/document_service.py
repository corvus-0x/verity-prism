from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.document_extraction import DocumentExtraction


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
