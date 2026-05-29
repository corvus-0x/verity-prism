from datetime import datetime

from pydantic import BaseModel, ConfigDict


class WorkspaceCreate(BaseModel):
    name: str
    description: str | None = None
    subject_name: str | None = None
    jurisdiction: str | None = None
    vertical: str = "general"

class WorkspaceUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    subject_name: str | None = None
    jurisdiction: str | None = None
    status: str | None = None

class WorkspaceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: str | None
    subject_name: str | None
    jurisdiction: str | None
    vertical: str
    status: str
    created_by: str
    created_at: datetime
    updated_at: datetime
