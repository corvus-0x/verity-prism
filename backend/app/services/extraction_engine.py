"""
Extraction engine — Claude-based document type detection and field extraction.

Extraction runs in batches of BATCH_SIZE fields so large schemas (370-field
parcel records, 235-field 990s) never hit Claude's output token limit.
Each batch is an independent Claude call; results are merged at the end.
"""

import json
import logging
import re
import time
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.document_extraction import DocumentExtraction
from app.models.document_schema import DocumentSchema
from app.services import claude_client
from app.services.claude_client import CHAT_MODEL, EXTRACTION_MODEL
from app.utils.json_helpers import strip_json_fences

logger = logging.getLogger(__name__)


class ExtractionBatchError(Exception):
    """Raised by _extract_batch when a Claude API call fails.
    Distinct from an empty result so callers can tell API failure from genuine
    zero-extraction (e.g., schema has no fields, or document has no matching data).
    """


# Fields per Claude extraction call. 40 fields × ~100 tokens each = ~4000 tokens
# output, well within the 8192 limit and leaving headroom for formatting.
BATCH_SIZE = 40

# Maximum OCR text characters sent per extraction batch.
# 200_000 chars ≈ 50k tokens — well within Claude Sonnet 4.6's context window.
# The old 4000-char cap silently dropped evidence from multi-page documents.
TEXT_LIMIT = 200_000


def _log_claude_call(
    call_type: str,
    latency_ms: int,
    prompt_chars: int,
    model: str = CHAT_MODEL,
    response=None,
    document_id: str | None = None,
    workspace_id: str | None = None,
    schema_id: str | None = None,
    attempt: int | None = None,
    error_message: str | None = None,
) -> None:
    """
    Write one row to claude_call_logs. Opens its own session so logging
    failures never corrupt the extraction transaction. Swallows all exceptions.
    """
    try:
        from app.database import SessionLocal
        from app.models.claude_call_log import ClaudeCallLog

        db = SessionLocal()
        try:
            usage = getattr(response, "usage", None)
            content = getattr(response, "content", None)
            row = ClaudeCallLog(
                call_type=call_type,
                document_id=document_id,
                workspace_id=workspace_id,
                schema_id=schema_id,
                model=model,
                attempt=attempt,
                success=response is not None,
                latency_ms=latency_ms,
                input_tokens=getattr(usage, "input_tokens", None),
                output_tokens=getattr(usage, "output_tokens", None),
                prompt_chars=prompt_chars,
                response_chars=len(content[0].text) if content else None,
                error_message=error_message,
            )
            db.add(row)
            db.commit()
        finally:
            db.close()
    except Exception as e:
        logger.warning(f"claude_call_log write failed: {e}")


def _load_known_types(db: Session) -> dict[str, str]:
    """Load active document types with display names for type detection.
    Returns {type_key: display_name} plus OTHER as a catch-all.
    Including display_name in the detection prompt prevents misclassification
    when type names are ambiguous (e.g. SCREENSHOT vs PARCEL-RECORD both arrive
    as image files — the display name clarifies which is which).
    """
    rows = (
        db.query(DocumentSchema.document_type, DocumentSchema.display_name)
        .filter(DocumentSchema.is_active == True)
        .distinct()
        .all()
    )
    result = {r[0]: r[1] for r in rows}
    result["OTHER"] = "Any document type not matched by the list above"
    return result


def _get_schema_for_vertical(
    doc_type: str,
    db: Session,
    workspace_vertical: str = "general",
) -> DocumentSchema | None:
    """
    Vertical-aware schema lookup helper (used by get_schema_for_type).
    """
    if workspace_vertical != "general":
        schema = (
            db.query(DocumentSchema)
            .filter(
                DocumentSchema.document_type == doc_type,
                DocumentSchema.vertical == workspace_vertical,
                DocumentSchema.is_active == True,
            )
            .first()
        )
        if schema:
            return schema
    return (
        db.query(DocumentSchema)
        .filter(
            DocumentSchema.document_type == doc_type,
            DocumentSchema.vertical == "general",
            DocumentSchema.is_active == True,
        )
        .first()
    )


def detect_document_type(ocr_text: str, db: Session, document_id: str | None = None) -> str:
    """
    Ask Claude to identify the document type from the first 1500 characters.
    Known types are loaded from document_schemas at call time — adding a
    schema row immediately makes that type detectable without redeployment.
    Type keys are shown with their display names so Claude can distinguish
    visually similar document types (e.g. SCREENSHOT vs PARCEL-RECORD).
    Falls back to 'OTHER' on any error or unrecognized type.
    """
    known_types = _load_known_types(db)
    type_list = "\n".join(f"- {t}: {desc}" for t, desc in known_types.items())

    prompt = f"""You are analyzing a document to identify its type.

Choose EXACTLY ONE type key from this list. Use the description to guide your choice:
{type_list}

The type key is the text before the colon (e.g. DEED, PARCEL-RECORD).
Choose based on the document's content and purpose, not its file format.
A screenshot of a county auditor website is PARCEL-RECORD, not SCREENSHOT.
SCREENSHOT is only for social media posts and general web page captures.

Respond with JSON only — no markdown, no explanation:
{{"document_type": "TYPE_HERE"}}

Document text (first 1500 characters):
{ocr_text[:1500]}"""

    start = time.time()
    response = None
    try:
        response = claude_client.get_client().messages.create(
            model="claude-sonnet-4-6",
            max_tokens=50,
            messages=[{"role": "user", "content": prompt}],
        )
        latency_ms = int((time.time() - start) * 1000)
        _log_claude_call(
            call_type="type_detection",
            latency_ms=latency_ms,
            prompt_chars=len(prompt),
            response=response,
            document_id=document_id,
        )
        result = json.loads(strip_json_fences(response.content[0].text))
        detected = result.get("document_type", "OTHER")
        return detected if detected in known_types else "OTHER"
    except Exception as e:
        latency_ms = int((time.time() - start) * 1000)
        _log_claude_call(
            call_type="type_detection",
            latency_ms=latency_ms,
            prompt_chars=len(prompt),
            response=response,
            document_id=document_id,
            error_message=str(e),
        )
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
    document_id: str | None = None,
    workspace_id: str | None = None,
    call_type: str = "extraction_batch",
    attempt: int = 1,
) -> list[dict]:
    """
    Ask Claude to extract a single batch of fields.
    Returns a list of extraction dicts with standardised keys:
    field_name, field_value, field_type, confidence, ocr_confidence.
    """
    fields_description = "\n".join(
        [f"- {f['name']} ({f['type']}): {f['description']}" for f in fields_batch]
    )

    if len(ocr_text) > TEXT_LIMIT:
        logger.warning(
            f"OCR text ({len(ocr_text)} chars) exceeds TEXT_LIMIT ({TEXT_LIMIT}); "
            "truncating for extraction"
        )

    # static_prompt is identical for every document of this schema, so it is
    # marked as a cacheable block below. The per-document text is a separate,
    # uncached block placed AFTER it — Anthropic prompt caching requires the
    # cached prefix to come first and stay byte-for-byte stable.
    static_prompt = f"""{schema.extraction_prompt or "Extract the following fields from this document."}

Extract ONLY these {len(fields_batch)} fields:
{fields_description}

Rules:
- Use EXACTLY these JSON key names: "field_name", "field_value", "field_type", "confidence", "ocr_confidence"
- field_value must be a string or null — never a number or boolean
- confidence: your certainty in the extraction (0.0 to 1.0)
- ocr_confidence: how clearly this field's text appeared in the source document (0.0 to 1.0). Low when source text is garbled, missing, or hard to read.
- Respond with JSON only — no markdown, no explanation

Required format:
{{"extractions": [
    {{"field_name": "exact_name_from_list", "field_value": "extracted text or null", "field_type": "text", "confidence": 0.9, "ocr_confidence": 0.95}},
    ...
]}}"""

    document_text = ocr_text[:TEXT_LIMIT]
    prompt_chars = len(static_prompt) + len(document_text)

    # Scale max_tokens to batch size: ~100 tokens per field + 200 overhead
    max_tokens = min(len(fields_batch) * 100 + 200, 4096)

    start = time.time()
    response = None
    try:
        static_block = {
            "type": "text",
            "text": static_prompt,
            "cache_control": {"type": "ephemeral"},
        }
        document_block = {
            "type": "text",
            "text": f"Document text:\n{document_text}",
        }
        response = claude_client.get_client().messages.create(
            model=EXTRACTION_MODEL,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": [static_block, document_block]}],
        )
        latency_ms = int((time.time() - start) * 1000)
        _log_claude_call(
            call_type=call_type,
            latency_ms=latency_ms,
            prompt_chars=prompt_chars,
            model=EXTRACTION_MODEL,
            response=response,
            document_id=document_id,
            workspace_id=workspace_id,
            schema_id=schema.id,
            attempt=attempt,
        )
        result = json.loads(strip_json_fences(response.content[0].text))
        raw = result.get("extractions", [])

        # Normalise key names — Claude sometimes returns field/value instead
        # of field_name/field_value despite explicit instructions
        normalised = []
        for item in raw:
            ai_conf_raw = item.get("confidence")
            ai_conf = ai_conf_raw if ai_conf_raw is not None else 1.0
            ocr_raw = item.get("ocr_confidence")
            normalised.append(
                {
                    "field_name": item.get("field_name") or item.get("field", ""),
                    "field_value": item.get("field_value") or item.get("value"),
                    "field_type": item.get("field_type", "text"),
                    "confidence": ai_conf,
                    "ocr_confidence": ocr_raw if ocr_raw is not None else ai_conf,
                }
            )
        return normalised
    except Exception as e:
        latency_ms = int((time.time() - start) * 1000)
        _log_claude_call(
            call_type=call_type,
            latency_ms=latency_ms,
            prompt_chars=prompt_chars,
            model=EXTRACTION_MODEL,
            response=response,
            document_id=document_id,
            workspace_id=workspace_id,
            schema_id=schema.id,
            attempt=attempt,
            error_message=str(e),
        )
        raise ExtractionBatchError(
            f"Batch extraction failed ({len(fields_batch)} fields): {e}"
        ) from e


def extract_fields(
    ocr_text: str,
    schema: DocumentSchema,
    document_id: str | None = None,
    workspace_id: str | None = None,
) -> list[dict]:
    """
    Extract all fields defined in the schema by running batched Claude calls.
    BATCH_SIZE fields per call prevents token-limit truncation on large schemas.
    Results from all batches are merged and returned as a single list.
    Raises ExtractionBatchError if every batch fails (distinguishes total API
    failure from a schema that legitimately has zero fields).
    """
    fields = schema.schema_fields
    if not fields:
        return []

    all_extractions: list[dict] = []
    batches = [fields[i : i + BATCH_SIZE] for i in range(0, len(fields), BATCH_SIZE)]
    batch_errors = 0

    for idx, batch in enumerate(batches):
        logger.debug(
            f"Extracting batch {idx + 1}/{len(batches)} "
            f"({len(batch)} fields) for schema {schema.document_type}"
        )
        try:
            batch_results = _extract_batch(
                ocr_text,
                batch,
                schema,
                document_id=document_id,
                workspace_id=workspace_id,
                call_type="extraction_batch",
                attempt=1,
            )
            all_extractions.extend(batch_results)
        except ExtractionBatchError:
            batch_errors += 1
            logger.warning(
                f"Batch {idx + 1}/{len(batches)} failed for schema {schema.document_type}"
            )

    # Any batch failures: retry missing fields once before giving up.
    # This covers both total failure (all batches failed) and partial failure
    # (some batches failed). The "raise all failed" guard runs after retry so
    # a transient error on every batch can still be recovered.
    if batch_errors > 0:
        extracted_names = {e["field_name"] for e in all_extractions}
        # f["name"] is the schema key; extracted_names uses Claude's response key "field_name"
        # — same string value, different dict keys (schema vs extraction output)
        retry_fields = [
            f for batch in batches for f in batch if f.get("name") not in extracted_names
        ]

        if retry_fields:
            logger.info(
                f"Retrying {len(retry_fields)} fields from partial failure "
                f"for schema {schema.document_type}"
            )
            retry_batches = [
                retry_fields[i : i + BATCH_SIZE] for i in range(0, len(retry_fields), BATCH_SIZE)
            ]
            retry_errors = 0
            for retry_batch in retry_batches:
                try:
                    retry_results = _extract_batch(
                        ocr_text,
                        retry_batch,
                        schema,
                        document_id=document_id,
                        workspace_id=workspace_id,
                        call_type="batch_retry_partial",
                        attempt=2,
                    )
                    all_extractions.extend(retry_results)
                except ExtractionBatchError:
                    retry_errors += 1
            if retry_errors > 0:
                logger.warning(
                    f"Partial retry: {retry_errors}/{len(retry_batches)} retry "
                    f"batch(es) still failing for schema {schema.document_type}"
                )

        if batch_errors == len(batches) and all_extractions:
            logger.warning(
                f"Total batch failure recovered partially by retry: "
                f"{len(all_extractions)} fields recovered for schema {schema.document_type}"
            )

    # After retry: if we still have nothing and every original batch failed,
    # the API is likely unavailable — raise so the pipeline marks the doc failed.
    if batch_errors == len(batches) and not all_extractions:
        raise ExtractionBatchError(
            f"All {len(batches)} extraction batch(es) failed for schema "
            f"{schema.document_type} — Claude API may be unavailable"
        )

    logger.info(
        f"Extraction complete: {len(all_extractions)} fields from "
        f"{len(batches)} batch(es) for schema {schema.document_type}"
    )
    return all_extractions


def _normalize_currency(value: str) -> str:
    """Strip currency symbols, commas, and whitespace; return a plain decimal string.
    For range values like '$100,000 - $150,000', takes the first numeric token.
    Returns the original string unchanged if no numeric value can be parsed.
    """
    cleaned = re.sub(r"[\$,\s]", "", value)
    if not cleaned:
        return value
    try:
        return f"{float(cleaned):.2f}"
    except ValueError:
        pass
    # Only use the prefix-match fallback for range separators (e.g. "100000-150000"),
    # not for unit suffixes like "1.5M" or "2.3B" — those would silently truncate.
    if re.search(r"[a-zA-Z]", cleaned):
        return value
    match = re.match(r"^(-?[\d.]+)", cleaned)
    if match:
        try:
            return f"{float(match.group(1)):.2f}"
        except ValueError:
            pass
    return value


def _normalize_date(value: str) -> str:
    """Parse common date formats and return ISO 8601 (YYYY-MM-DD).
    Tries a fixed list of formats in order; returns the original string if none match.
    """
    formats = [
        "%m/%d/%Y",
        "%m-%d-%Y",
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%B %d, %Y",
        "%b %d, %Y",
        "%B %d %Y",
        "%b %d %Y",
        "%d/%m/%Y",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(value, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return value


def _normalize_boolean(value: str) -> str:
    """Normalise truthy/falsy string variants to 'true' or 'false'."""
    return "true" if value.lower().strip() in {"yes", "true", "1", "y", "t"} else "false"


def _normalize_field_value(value: str | None, field_type: str) -> str | None:
    """Apply type-driven normalization to extracted values before storage.
    Currency → plain decimal string. Date → ISO 8601. Boolean → 'true'/'false'.
    All other types are stripped of leading/trailing whitespace only.
    Returns None for None input; returns '' for blank/whitespace-only input.
    """
    if value is None:
        return None
    stripped = value.strip()
    if not stripped:
        return stripped
    if field_type == "currency":
        return _normalize_currency(stripped)
    if field_type == "date":
        return _normalize_date(stripped)
    if field_type == "boolean":
        return _normalize_boolean(stripped)
    return stripped


def save_extractions(
    extractions: list[dict],
    document_id: str,
    workspace_id: str,
    schema_id: str,
    db: Session,
    attempt: int = 1,
) -> None:
    """
    Save each extracted field as one row in document_extractions.
    attempt=1 for initial extraction, attempt=2 for automated retry,
    attempt=3 for human correction (written by the review router).
    Tolerates both field_name/field_value and field/value key names
    from Claude in case normalisation in _extract_batch missed a variant.
    """
    for item in extractions:
        field_name = item.get("field_name") or item.get("field")
        if not field_name:
            continue
        field_value = item.get("field_value") or item.get("value")
        field_type = item.get("field_type", "text")
        field_value = _normalize_field_value(field_value, field_type)
        row = DocumentExtraction(
            document_id=document_id,
            workspace_id=workspace_id,
            field_name=field_name,
            field_value=field_value,
            field_type=field_type,
            confidence=item.get("confidence", 1.0),
            ocr_confidence=item.get("ocr_confidence", item.get("confidence", 1.0)),
            schema_id=schema_id,
            attempt=attempt,
        )
        db.add(row)
    db.commit()
