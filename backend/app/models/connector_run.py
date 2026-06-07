import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ConnectorRun(Base):
    __tablename__ = "connector_runs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    connector_id: Mapped[str] = mapped_column(String, nullable=False)  # machine key, e.g. "irs-teos"
    search_query: Mapped[str] = mapped_column(String, nullable=True)
    candidate_label: Mapped[str] = mapped_column(String, nullable=True)
    params: Mapped[dict] = mapped_column(JSONB, nullable=True)  # candidate_ref + item_refs
    status: Mapped[str] = mapped_column(String, nullable=False, default="running")  # running|complete|partial|failed
    result: Mapped[dict] = mapped_column(JSONB, nullable=True)  # per-item outcomes
    error_message: Mapped[str] = mapped_column(String, nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    deleted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
