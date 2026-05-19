from pydantic import BaseModel
from typing import Optional
from datetime import datetime, date


class TransactionCreate(BaseModel):
    transaction_type: str
    entity_from_id: Optional[str] = None
    entity_to_id: Optional[str] = None
    amount_paid: Optional[float] = None
    appraised_value: Optional[float] = None
    consideration: Optional[str] = None
    transaction_date: Optional[date] = None
    recorded_date: Optional[date] = None
    instrument_number: Optional[str] = None
    source_doc_id: Optional[str] = None
    notes: Optional[str] = None


class TransactionOut(BaseModel):
    id: str
    workspace_id: str
    transaction_type: str
    amount_paid: Optional[float]
    appraised_value: Optional[float]
    consideration: Optional[str]
    transaction_date: Optional[date]
    instrument_number: Optional[str]
    notes: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True
