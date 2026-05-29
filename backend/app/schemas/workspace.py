from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class WorkspaceCreate(BaseModel):
    name: str
    description: Optional[str] = None
    subject_name: Optional[str] = None
    jurisdiction: Optional[str] = None
    vertical: str = "general"

class WorkspaceUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    subject_name: Optional[str] = None
    jurisdiction: Optional[str] = None
    status: Optional[str] = None

class WorkspaceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: Optional[str]
    subject_name: Optional[str]
    jurisdiction: Optional[str]
    vertical: str
    status: str
    created_by: str
    created_at: datetime
    updated_at: datetime
