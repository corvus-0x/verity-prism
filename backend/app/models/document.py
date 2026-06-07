import uuid
from datetime import UTC, datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Index, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (
        Index("idx_documents_search_vector", "search_vector", postgresql_using="gin"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id: Mapped[str] = mapped_column(String, ForeignKey("workspaces.id"), nullable=False)
    filename: Mapped[str] = mapped_column(String, nullable=False)
    original_filename: Mapped[str] = mapped_column(String, nullable=False)
    file_path: Mapped[str] = mapped_column(String, nullable=False)
    file_type: Mapped[str] = mapped_column(
        SAEnum("pdf", "image", "csv", "text", "xml", "other", name="file_type"), nullable=False
    )
    sha256_hash: Mapped[str] = mapped_column(String, nullable=False)
    source_url: Mapped[str] = mapped_column(String, nullable=True)
    source_type: Mapped[str] = mapped_column(
        SAEnum("upload", "api_pull", "manual_entry", name="source_type"), default="upload"
    )
    source_ref: Mapped[str] = mapped_column(String, nullable=True)  # ConnectorRun.id that produced this doc (null for uploads)
    detected_doc_type: Mapped[str] = mapped_column(String, nullable=True)
    schema_id: Mapped[str] = mapped_column(String, ForeignKey("document_schemas.id"), nullable=True)
    ocr_text: Mapped[str] = mapped_column(Text, nullable=True)
    search_vector: Mapped[Any | None] = mapped_column(TSVECTOR, nullable=True)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=True)
    extraction_status: Mapped[str] = mapped_column(
        SAEnum("pending", "complete", "failed", "no_schema", "needs_review", name="extraction_status"), default="pending"
    )
    extraction_error: Mapped[str] = mapped_column(String, nullable=True)
    uploaded_by: Mapped[str] = mapped_column(String, ForeignKey("users.id"), nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    deleted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    flag_reason: Mapped[str] = mapped_column(String, nullable=True)
    flag_note: Mapped[str] = mapped_column(String, nullable=True)
    embedding: Mapped[Any | None] = mapped_column(Vector(1536), nullable=True)
