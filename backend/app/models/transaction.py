import uuid
from datetime import date, datetime, timezone

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id: Mapped[str] = mapped_column(String, ForeignKey("workspaces.id"), nullable=False)
    entity_from_id: Mapped[str] = mapped_column(String, ForeignKey("entities.id"), nullable=True)
    entity_to_id: Mapped[str] = mapped_column(String, ForeignKey("entities.id"), nullable=True)
    transaction_type: Mapped[str] = mapped_column(
        SAEnum("purchase", "transfer", "lien", "loan", "donation", "construction", "compensation",
               name="transaction_type"), nullable=False
    )
    amount_paid: Mapped[float] = mapped_column(Numeric(15, 2), nullable=True)
    appraised_value: Mapped[float] = mapped_column(Numeric(15, 2), nullable=True)
    consideration: Mapped[str] = mapped_column(
        SAEnum("zero", "below_market", "fair_market", "above_market", name="consideration_type"),
        nullable=True
    )
    transaction_date: Mapped[date] = mapped_column(Date, nullable=True)
    recorded_date: Mapped[date] = mapped_column(Date, nullable=True)
    instrument_number: Mapped[str] = mapped_column(String, nullable=True)
    source_doc_id: Mapped[str] = mapped_column(String, ForeignKey("documents.id"), nullable=True)
    notes: Mapped[str] = mapped_column(String, nullable=True)
    created_by: Mapped[str] = mapped_column(String, ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
