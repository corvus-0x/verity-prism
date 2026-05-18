import uuid
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, Enum as SAEnum, ForeignKey, ARRAY
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base

class SignalType(Base):
    __tablename__ = "signal_types"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    code: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=False)
    severity: Mapped[str] = mapped_column(
        SAEnum("critical", "high", "medium", "low", name="signal_severity"), nullable=False
    )
    relevant_to: Mapped[list] = mapped_column(ARRAY(String), default=list)

class Finding(Base):
    __tablename__ = "findings"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id: Mapped[str] = mapped_column(String, ForeignKey("workspaces.id"), nullable=False)
    signal_type_id: Mapped[str] = mapped_column(String, ForeignKey("signal_types.id"), nullable=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=True)
    severity: Mapped[str] = mapped_column(
        SAEnum("critical", "high", "medium", "low", name="finding_severity"), nullable=False
    )
    status: Mapped[str] = mapped_column(
        SAEnum("open", "confirmed", "dismissed", name="finding_status"), default="open"
    )
    created_by: Mapped[str] = mapped_column(String, ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class FindingEvidence(Base):
    __tablename__ = "finding_evidence"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    finding_id: Mapped[str] = mapped_column(String, ForeignKey("findings.id"), nullable=False)
    document_id: Mapped[str] = mapped_column(String, ForeignKey("documents.id"), nullable=True)
    entity_id: Mapped[str] = mapped_column(String, ForeignKey("entities.id"), nullable=True)
    note: Mapped[str] = mapped_column(String, nullable=True)
    added_by: Mapped[str] = mapped_column(String, ForeignKey("users.id"), nullable=False)
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
