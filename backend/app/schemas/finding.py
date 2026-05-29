from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict


class SignalTypeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    code: str
    name: str
    description: str
    severity: str
    relevant_to: List[str]

class FindingCreate(BaseModel):
    title: str
    description: Optional[str] = None
    severity: str
    signal_type_id: Optional[str] = None

class FindingUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    severity: Optional[str] = None
    status: Optional[str] = None

class FindingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    workspace_id: str
    signal_type_id: Optional[str]
    title: str
    description: Optional[str]
    severity: str
    status: str
    created_at: datetime
