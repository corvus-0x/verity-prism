from pydantic import BaseModel


class AutomationRateOut(BaseModel):
    total: int
    automated: int
    needs_review: int
    failed: int
    automation_rate: float   # automated / total, or 0.0 if total == 0


class DailyVolume(BaseModel):
    date: str   # ISO date "YYYY-MM-DD"
    inbound: int
    completed: int


class VolumeOut(BaseModel):
    days: list[DailyVolume]


class SchemaDetail(BaseModel):
    document_type: str
    total_documents: int
    avg_ai_confidence: float
    avg_ocr_confidence: float
    retry_rate: float       # fraction of docs that had attempt=2 rows
    correction_rate: float  # fraction of docs that had attempt=3 rows


class ClassificationDetailsOut(BaseModel):
    schemas: list[SchemaDetail]


class CurrentProcessingOut(BaseModel):
    pending: int
    needs_review: int
    total_active: int
