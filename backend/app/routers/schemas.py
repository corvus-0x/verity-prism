from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.document_schema import DocumentSchema
from app.models.user import User
from app.services.auth import get_current_user

router = APIRouter(prefix="/schemas", tags=["schemas"])


@router.get("/")
def list_schemas(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Return all active document schemas ordered by vertical then display name."""
    schemas = (
        db.query(DocumentSchema)
        .filter(DocumentSchema.is_active == True)
        .order_by(DocumentSchema.vertical, DocumentSchema.display_name)
        .all()
    )
    return [
        {
            "id": s.id,
            "document_type": s.document_type,
            "display_name": s.display_name,
            "vertical": s.vertical,
            "parse_strategy": s.parse_strategy,
            "default_confidence_threshold": s.default_confidence_threshold,
            "field_count": len(s.schema_fields or []),
            "fields": s.schema_fields or [],
            "version": s.version,
        }
        for s in schemas
    ]


@router.get("/{schema_id}")
def get_schema(
    schema_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Return a single active schema by ID with full field definitions."""
    schema = db.query(DocumentSchema).filter(
        DocumentSchema.id == schema_id,
        DocumentSchema.is_active == True,
    ).first()
    if not schema:
        raise HTTPException(status_code=404, detail="Schema not found")
    return {
        "id": schema.id,
        "document_type": schema.document_type,
        "display_name": schema.display_name,
        "vertical": schema.vertical,
        "parse_strategy": schema.parse_strategy,
        "default_confidence_threshold": schema.default_confidence_threshold,
        "field_count": len(schema.schema_fields or []),
        "fields": schema.schema_fields or [],
        "version": schema.version,
    }
