from pydantic import BaseModel


class ConnectorOut(BaseModel):
    id: str
    name: str
    description: str
    verticals: list[str]
    search_schema: dict


class SearchRequest(BaseModel):
    params: dict


class CandidateOut(BaseModel):
    ref: str
    display_name: str
    identifier: str = ""
    location: str = ""


class ListItemsRequest(BaseModel):
    candidate_ref: str


class FetchableItemOut(BaseModel):
    item_ref: str
    label: str
    year: int | None = None
    item_type: str = ""
    filed_date: str = ""


class FetchRequest(BaseModel):
    candidate_ref: str
    candidate_label: str = ""
    search_query: str = ""
    item_refs: list[str]


class RunOut(BaseModel):
    id: str
    connector_id: str
    search_query: str | None = None
    candidate_label: str | None = None
    status: str
    result: list | None = None
    error_message: str | None = None

    class Config:
        from_attributes = True
