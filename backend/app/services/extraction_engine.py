import json
import logging
from anthropic import Anthropic
from sqlalchemy.orm import Session
from app.config import settings
from app.models.document_schema import DocumentSchema
from app.models.document_extraction import DocumentExtraction

logger = logging.getLogger(__name__)

client = Anthropic(api_key=settings.anthropic_api_key)

KNOWN_DOCUMENT_TYPES = [
    "DEED", "PLAT", "990", "990-T", "UCC", "SOS-FILING", "BUILDING-PERMIT",
    "PARCEL-RECORD", "AUDIT-REPORT", "INSURANCE-FORM", "COURT-FILING",
    "CORRESPONDENCE", "OBITUARY", "NEWS-ARTICLE", "SCREENSHOT", "SPREADSHEET",
    "OTHER",
]


def detect_document_type(ocr_text: str) -> str:
    """Ask Claude to identify the document type from the first 1500 characters."""
    prompt = f"""You are analyzing a document to determine its type.
Based on the text below, identify the document type.

Choose EXACTLY ONE from this list:
{', '.join(KNOWN_DOCUMENT_TYPES)}

Respond with JSON only: {{"document_type": "TYPE_HERE"}}

Document text (first 1500 characters):
{ocr_text[:1500]}"""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=50,
            messages=[{"role": "user", "content": prompt}]
        )
        result = json.loads(response.content[0].text.strip())
        detected = result.get("document_type", "OTHER")
        return detected if detected in KNOWN_DOCUMENT_TYPES else "OTHER"
    except Exception as e:
        logger.warning(f"Type detection failed: {e}")
        return "OTHER"


def get_schema_for_type(doc_type: str, db: Session) -> DocumentSchema | None:
    """Look up the active extraction schema for this document type."""
    return db.query(DocumentSchema).filter(
        DocumentSchema.document_type == doc_type,
        DocumentSchema.is_active == True
    ).first()


def extract_fields(ocr_text: str, schema: DocumentSchema) -> list[dict]:
    """
    Ask Claude to extract every field defined in the schema.
    Returns a list of extraction dicts with field_name, field_value, field_type, confidence.
    """
    fields_description = "\n".join([
        f"- {f['name']} ({f['type']}): {f['description']}"
        for f in schema.schema_fields
    ])

    prompt = f"""{schema.extraction_prompt or 'Extract the following fields from this document.'}

Fields to extract:
{fields_description}

For each field, provide:
- field_name: the exact field name from the list above
- field_value: the extracted value as a string (null if not found)
- field_type: the type (name/date/currency/address/id_number/text/boolean)
- confidence: 0.0 to 1.0

Respond with JSON only:
{{"extractions": [
    {{"field_name": "...", "field_value": "...", "field_type": "...", "confidence": 0.95}},
    ...
]}}

Document text:
{ocr_text[:4000]}"""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}]
        )
        result = json.loads(response.content[0].text.strip())
        return result.get("extractions", [])
    except Exception as e:
        logger.warning(f"Field extraction failed for schema {schema.document_type}: {e}")
        return []


def save_extractions(
    extractions: list[dict],
    document_id: str,
    workspace_id: str,
    schema_id: str,
    db: Session,
) -> None:
    """Save each extracted field as one row in document_extractions."""
    for item in extractions:
        if not item.get("field_name"):
            continue
        row = DocumentExtraction(
            document_id=document_id,
            workspace_id=workspace_id,
            field_name=item["field_name"],
            field_value=item.get("field_value"),
            field_type=item.get("field_type", "text"),
            confidence=item.get("confidence", 1.0),
            schema_id=schema_id,
        )
        db.add(row)
    db.commit()
