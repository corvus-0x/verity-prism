from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class LeadCreate(BaseModel):
    question: str
    source: Optional[str] = None
    originated_by: str = "user"
    triggered_by_id: Optional[str] = None
    assigned_to: Optional[str] = None


class LeadUpdate(BaseModel):
    status: Optional[str] = None
    result_summary: Optional[str] = None
    source: Optional[str] = None


class LeadOut(BaseModel):
    id: str
    workspace_id: str
    question: str
    source: Optional[str]
    status: str
    originated_by: str
    triggered_by_id: Optional[str]
    result_summary: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True
