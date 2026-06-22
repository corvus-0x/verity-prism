from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_workspace_or_404
from app.models.user import User
from app.schemas.note import NoteCreate, NoteOut
from app.services import note_service
from app.services.auth import get_current_user

router = APIRouter(prefix="/workspaces/{workspace_id}/notes", tags=["notes"])


@router.post("/", response_model=NoteOut, status_code=201)
def create_note(
    workspace_id: str,
    payload: NoteCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    get_workspace_or_404(workspace_id, user, db)
    return note_service.create_note(db, workspace_id, user.id, payload)


@router.get("/", response_model=list[NoteOut])
def list_notes(
    workspace_id: str,
    entity_type: str | None = None,
    entity_id: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    get_workspace_or_404(workspace_id, user, db)
    return note_service.list_notes(db, workspace_id, entity_type, entity_id)
