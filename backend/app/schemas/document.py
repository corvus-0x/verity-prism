from datetime import datetime

from pydantic import BaseModel


class DocumentOut(BaseModel):
    id: str
    workspace_id: str
    filename: str
    original_filename: str
    file_type: str
    sha256_hash: str
    source_url: str | None
    source_type: str
    detected_doc_type: str | None
    extraction_status: str
    extraction_error: str | None
    size_bytes: int | None
    uploaded_at: datetime

    class Config:
        from_attributes = True


class ExtractionOut(BaseModel):
    id: str
    document_id: str
    field_name: str
    field_value: str | None
    field_type: str
    confidence: float
    attempt: int
    extracted_at: datetime

    class Config:
        from_attributes = True
