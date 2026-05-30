"""
Extraction evaluator — checks confidence scores after extraction and retries
low-confidence fields with a targeted mini-batch.

evaluate() is a pure function — no DB access, fully unit testable.
run_retry() builds the mini-batch, calls _extract_batch(), and saves results.
"""
import logging
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models.document_schema import DocumentSchema
from app.services.extraction_engine import _extract_batch, save_extractions, ExtractionBatchError

logger = logging.getLogger(__name__)


@dataclass
class EvaluationResult:
    low_confidence_fields: list[str]
    threshold_used: float
    total_fields: int

    @property
    def needs_review(self) -> bool:
        return len(self.low_confidence_fields) > 0


def evaluate(extractions: list[dict], threshold: float) -> EvaluationResult:
    """
    Identify fields whose confidence falls below the schema threshold.
    Pure function — takes the extracted list[dict], returns which field names failed.
    Does not read from or write to the database.
    """
    low = [
        e["field_name"]
        for e in extractions
        if e.get("field_name") and e.get("confidence", 1.0) < threshold
    ]
    return EvaluationResult(
        low_confidence_fields=low,
        threshold_used=threshold,
        total_fields=len(extractions),
    )


def run_retry(
    document_id: str,
    workspace_id: str,
    ocr_text: str,
    schema: DocumentSchema,
    low_confidence_field_names: list[str],
    db: Session,
) -> list[dict]:
    """
    Retry extraction for a targeted subset of low-confidence fields.
    Builds a mini-batch from the schema definition for only the failing fields,
    runs one Claude call, and saves results as attempt=2 rows.
    Returns the retry extractions list (may be empty if Claude fails).
    """
    # Build mini-batch: only schema fields that failed
    failing_set = set(low_confidence_field_names)
    fields_batch = [
        f for f in (schema.schema_fields or [])
        if f.get("name") in failing_set
    ]

    if not fields_batch:
        logger.warning(
            f"run_retry: no schema fields matched failing names {low_confidence_field_names} "
            f"for doc {document_id}"
        )
        return []

    logger.info(
        f"Retrying {len(fields_batch)} low-confidence fields for doc {document_id} "
        f"(schema: {schema.document_type})"
    )

    try:
        retry_extractions = _extract_batch(
            ocr_text=ocr_text,
            fields_batch=fields_batch,
            schema=schema,
            document_id=document_id,
            workspace_id=workspace_id,
            call_type="extraction_retry",
        )
    except ExtractionBatchError as e:
        logger.warning(f"Retry batch failed for doc {document_id}: {e}")
        return []

    if retry_extractions:
        save_extractions(retry_extractions, document_id, workspace_id, schema.id, db, attempt=2)

    return retry_extractions
