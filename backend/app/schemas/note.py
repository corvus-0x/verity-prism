from pydantic import BaseModel
from datetime import datetime


class NoteCreate(BaseModel):
    entity_type: str
    entity_id: str
    content: str


class NoteOut(BaseModel):
    id: str
    workspace_id: str
    entity_type: str
    entity_id: str
    content: str
    created_at: datetime

    class Config:
        from_attributes = True
