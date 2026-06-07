from datetime import date, datetime

from pydantic import BaseModel


class TransactionCreate(BaseModel):
    transaction_type: str
    entity_from_id: str | None = None
    entity_to_id: str | None = None
    amount_paid: float | None = None
    appraised_value: float | None = None
    consideration: str | None = None
    transaction_date: date | None = None
    recorded_date: date | None = None
    instrument_number: str | None = None
    source_doc_id: str | None = None
    notes: str | None = None


class TransactionOut(BaseModel):
    id: str
    workspace_id: str
    transaction_type: str
    amount_paid: float | None
    appraised_value: float | None
    consideration: str | None
    transaction_date: date | None
    instrument_number: str | None
    notes: str | None
    created_at: datetime

    class Config:
        from_attributes = True
