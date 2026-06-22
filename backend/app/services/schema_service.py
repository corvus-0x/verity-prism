from sqlalchemy import case
from sqlalchemy.orm import Session

from app.models.document_schema import DocumentSchema


def list_active_schemas(db: Session) -> list[DocumentSchema]:
    """Active schemas ordered by vertical (general first) then display name."""
    return (
        db.query(DocumentSchema)
        .filter(DocumentSchema.is_active == True)  # noqa: E712
        .order_by(
            case((DocumentSchema.vertical == "general", 0), else_=1),
            DocumentSchema.vertical,
            DocumentSchema.display_name,
        )
        .all()
    )


def get_active_schema(db: Session, schema_id: str) -> DocumentSchema | None:
    """Fetch a single active schema by id; None if not found."""
    return (
        db.query(DocumentSchema)
        .filter(
            DocumentSchema.id == schema_id,
            DocumentSchema.is_active == True,  # noqa: E712
        )
        .first()
    )
