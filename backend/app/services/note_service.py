from sqlalchemy.orm import Session

from app.models.note import Note
from app.schemas.note import NoteCreate


def create_note(db: Session, workspace_id: str, author_id: str, payload: NoteCreate) -> Note:
    """Create a note in a workspace. Caller authorizes the workspace first."""
    note = Note(**payload.model_dump(), workspace_id=workspace_id, author_id=author_id)
    db.add(note)
    db.commit()
    db.refresh(note)
    return note


def list_notes(
    db: Session,
    workspace_id: str,
    entity_type: str | None = None,
    entity_id: str | None = None,
) -> list[Note]:
    """List active notes in a workspace, optionally scoped to one entity.
    Filters is_deleted so soft-deleted notes never surface."""
    q = db.query(Note).filter(
        Note.workspace_id == workspace_id,
        Note.is_deleted == False,  # noqa: E712
    )
    if entity_type:
        q = q.filter(Note.entity_type == entity_type)
    if entity_id:
        q = q.filter(Note.entity_id == entity_id)
    return q.all()
