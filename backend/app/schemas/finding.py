from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SignalTypeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    code: str
    name: str
    description: str
    severity: str
    relevant_to: list[str]

class FindingCreate(BaseModel):
    title: str
    description: str | None = None
    severity: str
    signal_type_id: str | None = None

class FindingUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    severity: str | None = None
    status: str | None = None

class FindingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    workspace_id: str
    signal_type_id: str | None
    title: str
    description: str | None
    severity: str
    status: str
    created_at: datetime
