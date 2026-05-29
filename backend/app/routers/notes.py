
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.note import Note
from app.models.user import User
from app.routers.workspaces import get_workspace_or_404
from app.schemas.note import NoteCreate, NoteOut
from app.services.auth import get_current_user

router = APIRouter(prefix="/workspaces/{workspace_id}/notes", tags=["notes"])


@router.post("/", response_model=NoteOut, status_code=201)
def create_note(workspace_id: str, payload: NoteCreate,
                db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    get_workspace_or_404(workspace_id, user, db)
    note = Note(**payload.model_dump(), workspace_id=workspace_id, author_id=user.id)
    db.add(note)
    db.commit()
    db.refresh(note)
    return note


@router.get("/", response_model=list[NoteOut])
def list_notes(workspace_id: str,
               entity_type: str | None = None,
               entity_id: str | None = None,
               db: Session = Depends(get_db),
               user: User = Depends(get_current_user)):
    get_workspace_or_404(workspace_id, user, db)
    q = db.query(Note).filter(Note.workspace_id == workspace_id)
    if entity_type:
        q = q.filter(Note.entity_type == entity_type)
    if entity_id:
        q = q.filter(Note.entity_id == entity_id)
    return q.all()
