from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class DocumentOut(BaseModel):
    id: str
    workspace_id: str
    filename: str
    original_filename: str
    file_type: str
    sha256_hash: str
    source_url: Optional[str]
    source_type: str
    detected_doc_type: Optional[str]
    extraction_status: str
    extraction_error: Optional[str]
    size_bytes: Optional[int]
    uploaded_at: datetime

    class Config:
        from_attributes = True


class ExtractionOut(BaseModel):
    id: str
    document_id: str
    field_name: str
    field_value: Optional[str]
    field_type: str
    confidence: float
    extracted_at: datetime

    class Config:
        from_attributes = True
