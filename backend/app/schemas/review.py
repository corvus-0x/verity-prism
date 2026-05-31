from datetime import datetime

from pydantic import BaseModel


class ReviewQueueItem(BaseModel):
    document_id: str
    workspace_id: str
    filename: str
    detected_doc_type: str | None
    low_confidence_count: int
    uploaded_at: datetime

    class Config:
        from_attributes = True


class ExtractionCorrectionIn(BaseModel):
    field_value: str


class ExtractionCorrectionOut(BaseModel):
    id: str
    field_name: str
    field_value: str | None
    field_type: str
    confidence: float
    ocr_confidence: float
    attempt: int
    extracted_at: datetime

    class Config:
        from_attributes = True


class FlagDocumentIn(BaseModel):
    flag_reason: str   # "unknown_type" | "missing_pages" | "low_quality_scan" | "wrong_schema" | "other"
    flag_note: str | None = None


class FlagDocumentOut(BaseModel):
    id: str
    flag_reason: str | None
    flag_note: str | None
    extraction_status: str

    class Config:
        from_attributes = True
