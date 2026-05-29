from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class AuditLogOut(BaseModel):
    id: str
    action: str
    entity_type: Optional[str]
    entity_id: Optional[str]
    user_id: Optional[str]
    before_state: Optional[dict]
    after_state: Optional[dict]
    timestamp: datetime

    class Config:
        from_attributes = True


class AuditLogPage(BaseModel):
    entries: list[AuditLogOut]
    total: int
    page: int
    pages: int
