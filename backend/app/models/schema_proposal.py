import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class SchemaChangeProposal(Base):
    __tablename__ = "schema_change_proposals"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id: Mapped[str] = mapped_column(String, ForeignKey("workspaces.id"), nullable=False)
    document_id: Mapped[str] = mapped_column(String, ForeignKey("documents.id"), nullable=True)
    base_schema_id: Mapped[str] = mapped_column(
        String, ForeignKey("document_schemas.id"), nullable=True
    )
    proposal_type: Mapped[str] = mapped_column(
        SAEnum("new_schema", "schema_extension", name="proposal_type"), nullable=False
    )
    status: Mapped[str] = mapped_column(
        SAEnum("draft", "rejected", "applied", "failed", name="proposal_status"),
        default="draft",
        nullable=False,
    )
    proposed_schema: Mapped[dict] = mapped_column(JSONB, default=dict)
    proposed_fields: Mapped[list] = mapped_column(JSONB, default=list)
    rationale: Mapped[str] = mapped_column(Text, nullable=True)
    created_by_ai: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # Provenance — schema changes are engine-contract changes; record why this was proposed.
    model_id: Mapped[str] = mapped_column(String, nullable=True)
    prompt_version: Mapped[str] = mapped_column(String, nullable=True)
    proposer_inputs: Mapped[dict] = mapped_column(JSONB, default=dict)
    # Review tracking — independent of outcome status.
    reviewed_by: Mapped[str] = mapped_column(String, ForeignKey("users.id"), nullable=True)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    apply_error: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    deleted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
