import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class DocumentSchema(Base):
    __tablename__ = "document_schemas"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    document_type: Mapped[str] = mapped_column(String, nullable=False)
    vertical: Mapped[str] = mapped_column(String, default="general")
    display_name: Mapped[str] = mapped_column(String, nullable=False)
    schema_fields: Mapped[list] = mapped_column(JSONB, default=list)
    extraction_prompt: Mapped[str] = mapped_column(Text, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    parse_strategy: Mapped[str] = mapped_column(
        SAEnum("claude", "xml_direct", name="parse_strategy"),
        default="claude",
        nullable=False,
    )
    default_confidence_threshold: Mapped[float] = mapped_column(
        Float, default=0.7, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
