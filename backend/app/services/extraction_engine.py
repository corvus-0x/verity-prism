"""
Extraction engine — Claude-based document type detection and field extraction.

Extraction runs in batches of BATCH_SIZE fields so large schemas (370-field
parcel records, 235-field 990s) never hit Claude's output token limit.
Each batch is an independent Claude call; results are merged at the end.
"""
import json
import logging
from anthropic import Anthropic
from sqlalchemy.orm import Session
from app.config import settings
from app.models.document_schema import DocumentSchema
from app.models.document_extraction import DocumentExtraction
from app.utils.json_helpers import strip_json_fences

logger = logging.getLogger(__name__)
client = Anthropic(api_key=settings.anthropic_api_key)

# Fields per Claude extraction call. 40 fields × ~100 tokens each = ~4000 tokens
# output, well within the 8192 limit and leaving headroom for formatting.
BATCH_SIZE = 40

KNOWN_DOCUMENT_TYPES = [
    "DEED", "PLAT", "990", "990-T", "UCC", "SOS-FILING", "BUILDING-PERMIT",
    "PARCEL-RECORD", "AUDIT-REPORT", "INSURANCE-FORM", "COURT-FILING",
    "CORRESPONDENCE", "OBITUARY", "NEWS-ARTICLE", "SCREENSHOT", "SPREADSHEET",
    "OTHER",
]


def _get_schema_for_vertical(
    doc_type: str,
    db: Session,
    workspace_vertical: str = "general",
) -> DocumentSchema | None:
    """
    Vertical-aware schema lookup helper (used by get_schema_for_type).
    """
    if workspace_vertical != "general":
        schema = db.query(DocumentSchema).filter(
            DocumentSchema.document_type == doc_type,
            DocumentSchema.vertical == workspace_vertical,
            DocumentSchema.is_active == True,
        ).first()
        if schema:
            return schema
    return db.query(DocumentSchema).filter(
        DocumentSchema.document_type == doc_type,
        DocumentSchema.vertical == "general",
        DocumentSchema.is_active == True,
    ).first()


def detect_document_type(ocr_text: str) -> str:
    """
    Ask Claude to identify the document type from the first 1500 characters.
    Returns one of KNOWN_DOCUMENT_TYPES; falls back to 'OTHER' on any error.
    """
    prompt = f"""You are analyzing a document to determine its type.
Based on the text below, identify the document type.

Choose EXACTLY ONE from this list:
{', '.join(KNOWN_DOCUMENT_TYPES)}

Respond with JSON only — no markdown, no explanation:
{{"document_type": "TYPE_HERE"}}

Document text (first 1500 characters):
{ocr_text[:1500]}"""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=50,
            messages=[{"role": "user", "content": prompt}],
        )
        result = json.loads(strip_json_fences(response.content[0].text))
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
    Prefers vertical-specific schemas over general ones so verticals can
    override default extraction behaviour for any document type.
    Falls back to vertical='general' if no vertical-specific schema exists.
    """
    return _get_schema_for_vertical(doc_type, db, workspace_vertical)


def _extract_batch(
    ocr_text: str,
    fields_batch: list[dict],
    schema: DocumentSchema,
) -> list[dict]:
    """
    Ask Claude to extract a single batch of fields.
    Returns a list of extraction dicts with standardised keys:
    field_name, field_value, field_type, confidence.
    """
    fields_description = "\n".join([
        f"- {f['name']} ({f['type']}): {f['description']}"
        for f in fields_batch
    ])

    prompt = f"""{schema.extraction_prompt or 'Extract the following fields from this document.'}

Extract ONLY these {len(fields_batch)} fields:
{fields_description}

Rules:
- Use EXACTLY these JSON key names: "field_name", "field_value", "field_type", "confidence"
- field_value must be a string or null — never a number or boolean
- confidence is 0.0 to 1.0
- Respond with JSON only — no markdown, no explanation

Required format:
{{"extractions": [
    {{"field_name": "exact_name_from_list", "field_value": "extracted text or null", "field_type": "text", "confidence": 0.9}},
    ...
]}}

Document text:
{ocr_text[:4000]}"""

    # Scale max_tokens to batch size: ~100 tokens per field + 200 overhead
    max_tokens = min(len(fields_batch) * 100 + 200, 4096)

    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        result = json.loads(strip_json_fences(response.content[0].text))
        raw = result.get("extractions", [])

        # Normalise key names — Claude sometimes returns field/value instead
        # of field_name/field_value despite explicit instructions
        normalised = []
        for item in raw:
            normalised.append({
                "field_name": item.get("field_name") or item.get("field", ""),
                "field_value": item.get("field_value") or item.get("value"),
                "field_type": item.get("field_type", "text"),
                "confidence": item.get("confidence", 1.0),
            })
        return normalised
    except Exception as e:
        logger.warning(f"Batch extraction failed ({len(fields_batch)} fields): {e}")
        return []


def extract_fields(ocr_text: str, schema: DocumentSchema) -> list[dict]:
    """
    Extract all fields defined in the schema by running batched Claude calls.
    BATCH_SIZE fields per call prevents token-limit truncation on large schemas.
    Results from all batches are merged and returned as a single list.
    """
    fields = schema.schema_fields
    if not fields:
        return []

    all_extractions: list[dict] = []
    batches = [fields[i: i + BATCH_SIZE] for i in range(0, len(fields), BATCH_SIZE)]

    for idx, batch in enumerate(batches):
        logger.debug(
            f"Extracting batch {idx + 1}/{len(batches)} "
            f"({len(batch)} fields) for schema {schema.document_type}"
        )
        batch_results = _extract_batch(ocr_text, batch, schema)
        all_extractions.extend(batch_results)

    logger.info(
        f"Extraction complete: {len(all_extractions)} fields from "
        f"{len(batches)} batch(es) for schema {schema.document_type}"
    )
    return all_extractions


def save_extractions(
    extractions: list[dict],
    document_id: str,
    workspace_id: str,
    schema_id: str,
    db: Session,
) -> None:
    """
    Save each extracted field as one row in document_extractions.
    Tolerates both field_name/field_value and field/value key names
    from Claude in case normalisation in _extract_batch missed a variant.
    """
    for item in extractions:
        field_name = item.get("field_name") or item.get("field")
        if not field_name:
            continue
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
