import uuid
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, Enum as SAEnum, ForeignKey, Text, BigInteger
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base

class Document(Base):
    __tablename__ = "documents"

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
    detected_doc_type: Mapped[str] = mapped_column(String, nullable=True)
    schema_id: Mapped[str] = mapped_column(String, ForeignKey("document_schemas.id"), nullable=True)
    ocr_text: Mapped[str] = mapped_column(Text, nullable=True)
    search_vector: Mapped[str] = mapped_column(Text, nullable=True)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=True)
    extraction_status: Mapped[str] = mapped_column(
        SAEnum("pending", "complete", "failed", "no_schema", name="extraction_status"), default="pending"
    )
    extraction_error: Mapped[str] = mapped_column(String, nullable=True)
    uploaded_by: Mapped[str] = mapped_column(String, ForeignKey("users.id"), nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
