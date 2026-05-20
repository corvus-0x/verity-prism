import re
import logging
from anthropic import Anthropic
from app.config import settings

logger = logging.getLogger(__name__)
client = Anthropic(api_key=settings.anthropic_api_key)

DOC_TYPE_CODES = [
    "DEED", "PLAT", "990", "990-T", "UCC", "SOS-FILING", "BUILDING-PERMIT",
    "PARCEL-RECORD", "AUDIT-REPORT", "CORRESPONDENCE", "OBITUARY",
    "NEWS-ARTICLE", "SCREENSHOT", "OTHER",
]


def generate_standardized_name(ocr_text: str, original_filename: str, file_ext: str) -> str:
    """
    Ask Claude to generate a standardized filename.
    Format: YYYY-MM-DD_DOC-TYPE_PRIMARY-ENTITY_BRIEF-DESCRIPTION.ext
    """
    prompt = f"""Generate a standardized filename for this investigative document.

Format: YYYY-MM-DD_DOC-TYPE_PRIMARY-ENTITY_BRIEF-DESCRIPTION.{file_ext}

Rules:
- DATE: Most prominent date. Use UNKNOWN-DATE if none found.
- DOC-TYPE: Choose from: {', '.join(DOC_TYPE_CODES)}
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
