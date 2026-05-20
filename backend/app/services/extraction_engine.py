import json
import re
import logging
from anthropic import Anthropic
from sqlalchemy.orm import Session
from app.config import settings
from app.models.document_schema import DocumentSchema
from app.models.document_extraction import DocumentExtraction

logger = logging.getLogger(__name__)

client = Anthropic(api_key=settings.anthropic_api_key)

def _strip_json_fences(text: str) -> str:
    """
    Remove markdown code fences that Claude sometimes wraps JSON in.
    '```json\\n{...}\\n```' → '{...}'
    """
    text = text.strip()
    if text.startswith("```"):
        # Find the first newline after the opening fence
        start = text.find("\n")
        if start != -1:
            text = text[start:].strip()
        # Remove closing fence
        if text.endswith("```"):
            text = text[: text.rfind("```")].strip()
    return text


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
        result = json.loads(_strip_json_fences(response.content[0].text))
        detected = result.get("document_type", "OTHER")
        return detected if detected in KNOWN_DOCUMENT_TYPES else "OTHER"
    except Exception as e:
        logger.warning(f"Type detection failed: {e}")
        return "OTHER"


def get_schema_for_type(
    doc_type: str,
    db: Session,
    workspace_vertical: str = "general",
) -> DocumentSchema | None:
    """
    Look up the active extraction schema for this document type.

    Prefers a vertical-specific schema over a general one so verticals can
    override the default extraction behaviour for any document type.
    Falls back to vertical='general' if no vertical-specific schema exists.
    """
    # 1. Try vertical-specific schema first
    if workspace_vertical != "general":
        schema = db.query(DocumentSchema).filter(
            DocumentSchema.document_type == doc_type,
            DocumentSchema.vertical == workspace_vertical,
            DocumentSchema.is_active == True,
        ).first()
        if schema:
            return schema

    # 2. Fall back to general schema
    return db.query(DocumentSchema).filter(
        DocumentSchema.document_type == doc_type,
        DocumentSchema.vertical == "general",
        DocumentSchema.is_active == True,
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
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}]
        )
        result = json.loads(_strip_json_fences(response.content[0].text))
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
    """
    Save each extracted field as one row in document_extractions.
    Handles key name variants Claude sometimes returns:
    field_name/field_value (expected) OR field/value (also seen).
    """
    for item in extractions:
        # Accept both field_name and field
        field_name = item.get("field_name") or item.get("field")
        if not field_name:
            continue
        # Accept both field_value and value
        field_value = item.get("field_value") or item.get("value")
        row = DocumentExtraction(
            document_id=document_id,
            workspace_id=workspace_id,
            field_name=field_name,
            field_value=field_value,
            field_type=item.get("field_type", "text"),
            confidence=item.get("confidence", 1.0),
            schema_id=schema_id,
        )
        db.add(row)
    db.commit()
