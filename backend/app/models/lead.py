import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class InvestigationLead(Base):
    __tablename__ = "investigation_leads"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id: Mapped[str] = mapped_column(String, ForeignKey("workspaces.id"), nullable=False)
    question: Mapped[str] = mapped_column(String, nullable=False)
    source: Mapped[str] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(
        SAEnum("pending", "in_progress", "complete", "dead_end", name="lead_status"), default="pending"
    )
    originated_by: Mapped[str] = mapped_column(
        SAEnum("user", "ai", "external_tip", name="lead_origin"), default="user"
    )
    triggered_by_id: Mapped[str] = mapped_column(
        String, ForeignKey("investigation_leads.id"), nullable=True
    )
    assigned_to: Mapped[str] = mapped_column(String, ForeignKey("users.id"), nullable=True)
    result_summary: Mapped[str] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
