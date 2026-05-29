from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class EntityCreate(BaseModel):
    type: str
    name: str
    status: str = "active"
    data: dict = {}

class EntityUpdate(BaseModel):
    name: Optional[str] = None
    status: Optional[str] = None
    data: Optional[dict] = None

class EntityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    workspace_id: str
    type: str
    name: str
    status: str
    data: dict
    created_at: datetime

class RelationshipCreate(BaseModel):
    entity_a_id: str
    entity_b_id: str
    type: str
    description: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    source_doc_id: Optional[str] = None

class RelationshipOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    workspace_id: str
    entity_a_id: str
    entity_b_id: str
    type: str
    description: Optional[str]
    created_at: datetime
