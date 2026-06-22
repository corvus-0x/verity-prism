from datetime import datetime
from typing import Literal

from pydantic import BaseModel

# Mirror the DB enums (models/lead.py): a 422 at the boundary beats a 500 when
# Postgres rejects the enum on insert.
LeadStatus = Literal["pending", "in_progress", "complete", "dead_end"]
LeadOrigin = Literal["user", "ai", "external_tip"]


class LeadCreate(BaseModel):
    question: str
    source: str | None = None
    originated_by: LeadOrigin = "user"
    triggered_by_id: str | None = None
    assigned_to: str | None = None


class LeadUpdate(BaseModel):
    status: LeadStatus | None = None
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
