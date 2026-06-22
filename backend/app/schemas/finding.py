from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

# Mirror the DB enums (models/finding.py): a 422 at the boundary beats a 500
# when Postgres rejects the enum on insert.
FindingSeverity = Literal["critical", "high", "medium", "low"]
FindingStatus = Literal["open", "confirmed", "dismissed"]


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
    severity: FindingSeverity
    signal_type_id: str | None = None


class FindingUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    severity: FindingSeverity | None = None
    status: FindingStatus | None = None


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
