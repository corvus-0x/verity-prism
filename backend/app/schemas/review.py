from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class ReviewQueueItem(BaseModel):
    document_id: str
    workspace_id: str
    filename: str
    detected_doc_type: Optional[str]
    low_confidence_count: int
    uploaded_at: datetime

    class Config:
        from_attributes = True


class ExtractionCorrectionIn(BaseModel):
    field_value: str


class ExtractionCorrectionOut(BaseModel):
    id: str
    field_name: str
    field_value: Optional[str]
    field_type: str
    confidence: float
    attempt: int
    extracted_at: datetime

    class Config:
        from_attributes = True
