from datetime import datetime

from pydantic import BaseModel


class LeadCreate(BaseModel):
    question: str
    source: str | None = None
    originated_by: str = "user"
    triggered_by_id: str | None = None
    assigned_to: str | None = None


class LeadUpdate(BaseModel):
    status: str | None = None
    result_summary: str | None = None
    source: str | None = None


class LeadOut(BaseModel):
    id: str
    workspace_id: str
    question: str
    source: str | None
    status: str
    originated_by: str
    triggered_by_id: str | None
    result_summary: str | None
    created_at: datetime

    class Config:
        from_attributes = True
