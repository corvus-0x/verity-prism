import logging
import re

from anthropic import Anthropic
from sqlalchemy.orm import Session

from app.config import settings
from app.models.document_schema import DocumentSchema

logger = logging.getLogger(__name__)
client = Anthropic(api_key=settings.anthropic_api_key)


def generate_standardized_name(ocr_text: str, original_filename: str, file_ext: str, db: Session) -> str:
    """
    Ask Claude to generate a standardized filename.
    Format: YYYY-MM-DD_DOC-TYPE_PRIMARY-ENTITY_BRIEF-DESCRIPTION.ext

    Loads valid DOC-TYPE codes from document_schemas so the list stays in
    sync with the database without requiring a code deploy.
    """
    rows = (
        db.query(DocumentSchema.document_type)
        .filter(DocumentSchema.is_active == True)
        .distinct()
        .all()
    )
    doc_type_codes = [r[0] for r in rows] + ["OTHER"]

    prompt = f"""Generate a standardized filename for this investigative document.

Format: YYYY-MM-DD_DOC-TYPE_PRIMARY-ENTITY_BRIEF-DESCRIPTION.{file_ext}

Rules:
- DATE: Most prominent date. Use UNKNOWN-DATE if none found.
- DOC-TYPE: Choose from: {', '.join(doc_type_codes)}
- PRIMARY-ENTITY: Main organization or person. CamelCase, no spaces.
- BRIEF-DESCRIPTION: 2-5 words, hyphens only, no spaces.
- Only letters, numbers, hyphens, underscores, and dots.

Original filename: {original_filename}

Document text (first 1500 chars):
{ocr_text[:1500]}

Respond with ONLY the filename. No explanation."""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=100,
            messages=[{"role": "user", "content": prompt}]
        )
        name = response.content[0].text.strip()
        name = re.sub(r"[^\w\-.]", "", name)
        return name if name else f"UNKNOWN-DATE_OTHER_{original_filename}"
    except Exception as e:
        logger.warning(f"Filename generation failed: {e}")
        return f"UNKNOWN-DATE_OTHER_{original_filename}"
