import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class DocumentExtraction(Base):
    __tablename__ = "document_extractions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    document_id: Mapped[str] = mapped_column(String, ForeignKey("documents.id"), nullable=False)
    workspace_id: Mapped[str] = mapped_column(String, ForeignKey("workspaces.id"), nullable=False)
    field_name: Mapped[str] = mapped_column(String, nullable=False)
    field_value: Mapped[str] = mapped_column(String, nullable=True)
    field_type: Mapped[str] = mapped_column(
        SAEnum("name", "date", "currency", "address", "id_number", "text", "boolean",
               name="extraction_field_type"),
        default="text"
    )
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    ocr_confidence: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    attempt: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    schema_id: Mapped[str] = mapped_column(String, ForeignKey("document_schemas.id"), nullable=True)
    extracted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
