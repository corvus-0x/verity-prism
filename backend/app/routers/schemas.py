from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.document_schema import DocumentSchema
from app.models.user import User
from app.services import schema_service
from app.services.auth import get_current_user

router = APIRouter(prefix="/schemas", tags=["schemas"])


def _serialize(s: DocumentSchema) -> dict:
    return {
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


@router.get("/")
def list_schemas(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Return all active document schemas ordered by vertical then display name."""
    return [_serialize(s) for s in schema_service.list_active_schemas(db)]


@router.get("/{schema_id}")
def get_schema(
    schema_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Return a single active schema by ID with full field definitions."""
    schema = schema_service.get_active_schema(db, schema_id)
    if not schema:
        raise HTTPException(status_code=404, detail="Schema not found")
    return _serialize(schema)
