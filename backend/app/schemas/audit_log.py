from datetime import datetime

from pydantic import BaseModel


class AuditLogOut(BaseModel):
    id: str
    action: str
    entity_type: str | None
    entity_id: str | None
    user_id: str | None
    before_state: dict | None
    after_state: dict | None
    timestamp: datetime

    class Config:
        from_attributes = True


class AuditLogPage(BaseModel):
    entries: list[AuditLogOut]
    total: int
    page: int
    pages: int
