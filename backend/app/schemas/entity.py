from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

# Mirror the DB enums (models/entity.py) so invalid values are a 422 at the HTTP
# boundary instead of a 500 when Postgres rejects the enum on insert.
EntityType = Literal["person", "organization", "property", "financial_account"]
EntityStatus = Literal["active", "dissolved", "deceased", "unknown"]


class EntityCreate(BaseModel):
    type: EntityType
    name: str
    status: EntityStatus = "active"
    data: dict = {}


class EntityUpdate(BaseModel):
    name: str | None = None
    status: EntityStatus | None = None
    data: dict | None = None


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
    description: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    source_doc_id: str | None = None


class RelationshipOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    workspace_id: str
    entity_a_id: str
    entity_b_id: str
    type: str
    description: str | None
    created_at: datetime
