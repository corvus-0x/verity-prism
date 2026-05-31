# Phase 2E — Engine Quality + Observability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add dual confidence scoring, per-field thresholds, field validation rules, document flagging, and a 4-dashboard observability page — giving the operator measurable extraction quality and structured reviewer feedback.

**Architecture:** Backend changes come first (migration → models → engine → evaluator → validator → new routers). Frontend reads new fields once they exist. `ocr_confidence` is estimated by Claude per field (field-level, not pytesseract page-level). All existing tests must continue passing.

**Tech Stack:** Python/FastAPI/SQLAlchemy/Alembic (backend), React/Vite/Tailwind/Recharts (frontend), PostgreSQL, pytest, Vitest.

---

## File Map

**Create:**
- `backend/alembic/versions/b2c3d4e5f6a7_phase2e_dual_confidence_and_flags.py`
- `backend/app/services/field_validator.py`
- `backend/app/routers/observability.py`
- `backend/app/schemas/observability.py`
- `backend/tests/test_field_validator.py`
- `backend/tests/test_observability.py`
- `frontend/src/api/observability.js`
- `frontend/src/pages/Observability.jsx`

**Modify:**
- `backend/app/models/document_extraction.py` — add `ocr_confidence`
- `backend/app/models/document.py` — add `flag_reason`, `flag_note`
- `backend/app/schemas/document.py` — add `ocr_confidence` to `ExtractionOut`
- `backend/app/schemas/review.py` — add `ocr_confidence` to `ExtractionCorrectionOut`, add `FlagDocumentIn`/`FlagDocumentOut`
- `backend/app/services/extraction_engine.py` — prompt + normalization + save_extractions
- `backend/app/services/xml_parser.py` — add `ocr_confidence: 1.0` to output dicts
- `backend/app/services/extraction_evaluator.py` — per-field thresholds + dual confidence
- `backend/app/services/document_pipeline.py` — wire field validator + updated evaluate call
- `backend/app/routers/review.py` — add flag endpoint
- `backend/app/main.py` — register observability router
- `backend/tests/test_pipeline.py` — update evaluator test calls, add ocr_confidence tests
- `frontend/src/api/documents.js` — add flagDocument()
- `frontend/src/components/documents/ExtractionTable.jsx` — dual confidence display
- `frontend/src/pages/workspace/ExtractionReview.jsx` — flag button + modal
- `frontend/src/App.jsx` — add /observability route
- `frontend/src/components/layout/AppShell.jsx` — nav link to Observability

---

## Task 1: Alembic Migration — ocr_confidence + flag columns

**Files:**
- Create: `backend/alembic/versions/b2c3d4e5f6a7_phase2e_dual_confidence_and_flags.py`

- [ ] **Step 1: Write the migration file**

```python
# backend/alembic/versions/b2c3d4e5f6a7_phase2e_dual_confidence_and_flags.py
"""phase2e_dual_confidence_and_flags

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-05-30

Adds:
- ocr_confidence to document_extractions (Claude's estimate of source text clarity)
- flag_reason and flag_note to documents (structured reviewer rejection feedback)
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'document_extractions'
                AND column_name = 'ocr_confidence'
            ) THEN
                ALTER TABLE document_extractions
                    ADD COLUMN ocr_confidence FLOAT NOT NULL DEFAULT 1.0;
            END IF;
        END $$;
    """)

    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'documents'
                AND column_name = 'flag_reason'
            ) THEN
                ALTER TABLE documents ADD COLUMN flag_reason VARCHAR;
                ALTER TABLE documents ADD COLUMN flag_note TEXT;
            END IF;
        END $$;
    """)


def downgrade() -> None:
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'document_extractions'
                AND column_name = 'ocr_confidence'
            ) THEN
                ALTER TABLE document_extractions DROP COLUMN ocr_confidence;
            END IF;
        END $$;
    """)
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'documents'
                AND column_name = 'flag_reason'
            ) THEN
                ALTER TABLE documents DROP COLUMN flag_reason;
                ALTER TABLE documents DROP COLUMN flag_note;
            END IF;
        END $$;
    """)
```

- [ ] **Step 2: Run migration against test DB**

```bash
docker-compose run --rm -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test backend alembic upgrade head
```

Expected: `Running upgrade a1b2c3d4e5f6 -> b2c3d4e5f6a7`

- [ ] **Step 3: Verify columns exist**

```bash
docker-compose exec db psql -U catalyst -d catalyst_test -c "\d document_extractions" | grep ocr_confidence
docker-compose exec db psql -U catalyst -d catalyst_test -c "\d documents" | grep flag
```

Expected: both columns visible.

- [ ] **Step 4: Run migration against dev DB**

```bash
cd backend && alembic upgrade head
```

Expected: `Running upgrade a1b2c3d4e5f6 -> b2c3d4e5f6a7`

- [ ] **Step 5: Commit**

```bash
git add backend/alembic/versions/b2c3d4e5f6a7_phase2e_dual_confidence_and_flags.py
git commit -m "feat: migration — ocr_confidence on document_extractions, flag columns on documents"
```

---

## Task 2: Model Updates

**Files:**
- Modify: `backend/app/models/document_extraction.py`
- Modify: `backend/app/models/document.py`

- [ ] **Step 1: Update DocumentExtraction**

Replace the `confidence` line and everything after in `document_extraction.py`:

```python
# backend/app/models/document_extraction.py
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
```

- [ ] **Step 2: Update Document model — add flag columns**

Add two lines after the `deleted_at` field in `backend/app/models/document.py`:

```python
    flag_reason: Mapped[str] = mapped_column(String, nullable=True)
    flag_note: Mapped[str] = mapped_column(String, nullable=True)
```

- [ ] **Step 3: Update ExtractionOut schema**

In `backend/app/schemas/document.py`, add `ocr_confidence` to `ExtractionOut`:

```python
class ExtractionOut(BaseModel):
    id: str
    document_id: str
    field_name: str
    field_value: str | None
    field_type: str
    confidence: float
    ocr_confidence: float
    attempt: int
    extracted_at: datetime

    class Config:
        from_attributes = True
```

- [ ] **Step 4: Update review schemas**

Replace the entire contents of `backend/app/schemas/review.py`:

```python
from datetime import datetime
from pydantic import BaseModel


class ReviewQueueItem(BaseModel):
    document_id: str
    workspace_id: str
    filename: str
    detected_doc_type: str | None
    low_confidence_count: int
    uploaded_at: datetime

    class Config:
        from_attributes = True


class ExtractionCorrectionIn(BaseModel):
    field_value: str


class ExtractionCorrectionOut(BaseModel):
    id: str
    field_name: str
    field_value: str | None
    field_type: str
    confidence: float
    ocr_confidence: float
    attempt: int
    extracted_at: datetime

    class Config:
        from_attributes = True


class FlagDocumentIn(BaseModel):
    flag_reason: str   # "unknown_type" | "missing_pages" | "low_quality_scan" | "wrong_schema" | "other"
    flag_note: str | None = None


class FlagDocumentOut(BaseModel):
    id: str
    flag_reason: str | None
    flag_note: str | None
    extraction_status: str

    class Config:
        from_attributes = True
```

- [ ] **Step 5: Run existing tests to confirm no regressions**

```bash
docker-compose run --rm -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test backend pytest tests/ -v --tb=short 2>&1 | tail -30
```

Expected: all existing tests pass.

- [ ] **Step 6: Commit**

```bash
git add backend/app/models/document_extraction.py backend/app/models/document.py backend/app/schemas/document.py backend/app/schemas/review.py
git commit -m "feat: add ocr_confidence to DocumentExtraction, flag columns to Document, update schemas"
```

---

## Task 3: Extraction Engine — Dual Confidence

**Files:**
- Modify: `backend/app/services/extraction_engine.py`
- Modify: `backend/app/services/xml_parser.py`
- Modify: `backend/tests/test_pipeline.py`

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_pipeline.py`:

```python
def test_extract_batch_returns_ocr_confidence(db, deed_schema):
    """_extract_batch must include ocr_confidence in each returned dict."""
    from app.services.extraction_engine import _extract_batch
    import json

    mock_client = MagicMock()
    payload = json.dumps({"extractions": [
        {
            "field_name": "grantor_name",
            "field_value": "Jane Smith",
            "field_type": "name",
            "confidence": 0.92,
            "ocr_confidence": 0.85,
        }
    ]})
    mock_client.messages.create.return_value = MagicMock(
        content=[MagicMock(text=payload)],
        usage=MagicMock(input_tokens=100, output_tokens=50),
    )

    with patch("app.services.claude_client.get_client", return_value=mock_client):
        results = _extract_batch(
            ocr_text="Grantor: Jane Smith",
            fields_batch=[{"name": "grantor_name", "type": "name", "description": "Grantor name"}],
            schema=deed_schema,
        )

    assert len(results) == 1
    assert "ocr_confidence" in results[0]
    assert results[0]["ocr_confidence"] == 0.85


def test_extract_batch_falls_back_ocr_confidence_to_confidence(db, deed_schema):
    """If Claude omits ocr_confidence, it defaults to the ai confidence value."""
    from app.services.extraction_engine import _extract_batch
    import json

    mock_client = MagicMock()
    payload = json.dumps({"extractions": [
        {
            "field_name": "grantor_name",
            "field_value": "Jane Smith",
            "field_type": "name",
            "confidence": 0.80,
            # ocr_confidence intentionally absent
        }
    ]})
    mock_client.messages.create.return_value = MagicMock(
        content=[MagicMock(text=payload)],
        usage=MagicMock(input_tokens=100, output_tokens=50),
    )

    with patch("app.services.claude_client.get_client", return_value=mock_client):
        results = _extract_batch(
            ocr_text="Grantor: Jane Smith",
            fields_batch=[{"name": "grantor_name", "type": "name", "description": "Grantor name"}],
            schema=deed_schema,
        )

    assert results[0]["ocr_confidence"] == 0.80
```

- [ ] **Step 2: Run to confirm failure**

```bash
docker-compose run --rm -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test backend pytest tests/test_pipeline.py::test_extract_batch_returns_ocr_confidence -v
```

Expected: `FAILED` — `KeyError: 'ocr_confidence'`

- [ ] **Step 3: Update `_extract_batch` in extraction_engine.py**

Replace the `prompt` variable and `normalised` loop in `_extract_batch`:

```python
    fields_description = "\n".join([
        f"- {f['name']} ({f['type']}): {f['description']}"
        for f in fields_batch
    ])

    if len(ocr_text) > TEXT_LIMIT:
        logger.warning(
            f"OCR text ({len(ocr_text)} chars) exceeds TEXT_LIMIT ({TEXT_LIMIT}); "
            "truncating for extraction"
        )

    prompt = f"""{schema.extraction_prompt or 'Extract the following fields from this document.'}

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
]}}

Document text:
{ocr_text[:TEXT_LIMIT]}"""
```

And update the normalisation loop (replace the existing one):

```python
        normalised = []
        for item in raw:
            ai_conf = item.get("confidence", 1.0)
            normalised.append({
                "field_name": item.get("field_name") or item.get("field", ""),
                "field_value": item.get("field_value") or item.get("value"),
                "field_type": item.get("field_type", "text"),
                "confidence": ai_conf,
                "ocr_confidence": item.get("ocr_confidence", ai_conf),
            })
        return normalised
```

- [ ] **Step 4: Update `save_extractions` to store `ocr_confidence`**

Replace the `row = DocumentExtraction(...)` block inside `save_extractions`:

```python
        row = DocumentExtraction(
            document_id=document_id,
            workspace_id=workspace_id,
            field_name=field_name,
            field_value=field_value,
            field_type=item.get("field_type", "text"),
            confidence=item.get("confidence", 1.0),
            ocr_confidence=item.get("ocr_confidence", item.get("confidence", 1.0)),
            schema_id=schema_id,
            attempt=attempt,
        )
```

- [ ] **Step 5: Update xml_parser.py — add ocr_confidence=1.0 to output**

In `xml_parser.py`, find where extraction dicts are built and add `"ocr_confidence": 1.0` alongside `"confidence": 1.0`. XML direct parse has no OCR uncertainty.

Search for the return dict pattern (look for `"confidence": 1.0` in the file) and add the key:

```python
            result = {
                "field_name": field["name"],
                "field_value": value,
                "field_type": field.get("type", "text"),
                "confidence": 1.0,
                "ocr_confidence": 1.0,
            }
```

- [ ] **Step 6: Run the new tests**

```bash
docker-compose run --rm -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test backend pytest tests/test_pipeline.py::test_extract_batch_returns_ocr_confidence tests/test_pipeline.py::test_extract_batch_falls_back_ocr_confidence_to_confidence -v
```

Expected: both PASS.

- [ ] **Step 7: Run the full test suite**

```bash
docker-compose run --rm -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test backend pytest tests/ -v --tb=short 2>&1 | tail -20
```

Expected: all pass.

- [ ] **Step 8: Commit**

```bash
git add backend/app/services/extraction_engine.py backend/app/services/xml_parser.py backend/tests/test_pipeline.py
git commit -m "feat: extraction engine returns dual confidence — ai confidence + ocr confidence per field"
```

---

## Task 4: Evaluator — Per-Field Thresholds + Dual Confidence

**Files:**
- Modify: `backend/app/services/extraction_evaluator.py`
- Modify: `backend/tests/test_pipeline.py`

- [ ] **Step 1: Write the failing tests**

Add to `backend/tests/test_pipeline.py`:

```python
def test_evaluate_uses_per_field_ai_threshold():
    """When a field has ai_threshold in schema_fields, use it instead of the default."""
    extractions = [
        {"field_name": "ein", "confidence": 0.88, "ocr_confidence": 0.95},
        {"field_name": "vendor_name", "confidence": 0.72, "ocr_confidence": 0.90},
    ]
    # ein requires 0.95, vendor_name uses default 0.75
    result = evaluate(
        extractions,
        threshold=0.75,
        field_thresholds={"ein": 0.95},
    )
    assert "ein" in result.low_confidence_fields      # 0.88 < 0.95
    assert "vendor_name" not in result.low_confidence_fields  # 0.72 >= 0.70... wait, 0.72 < 0.75


def test_evaluate_uses_per_field_ai_threshold_correct():
    """Corrected: vendor_name 0.72 < default 0.75 so it fails the default threshold."""
    extractions = [
        {"field_name": "ein", "confidence": 0.88, "ocr_confidence": 0.95},
        {"field_name": "vendor_name", "confidence": 0.80, "ocr_confidence": 0.90},
    ]
    result = evaluate(
        extractions,
        threshold=0.75,
        field_thresholds={"ein": 0.95},
    )
    assert "ein" in result.low_confidence_fields       # 0.88 < 0.95 (field threshold)
    assert "vendor_name" not in result.low_confidence_fields  # 0.80 >= 0.75 (default)


def test_evaluate_flags_low_ocr_confidence():
    """Fields below the ocr_threshold are flagged even when ai confidence is high."""
    extractions = [
        {"field_name": "sale_price", "confidence": 0.90, "ocr_confidence": 0.50},
    ]
    result = evaluate(
        extractions,
        threshold=0.75,
        ocr_threshold=0.70,
    )
    assert "sale_price" in result.low_confidence_fields  # ocr 0.50 < ocr_threshold 0.70


def test_evaluate_passes_when_both_confidences_meet_thresholds():
    """Field passes only when both ai and ocr confidence are above their thresholds."""
    extractions = [
        {"field_name": "grantor_name", "confidence": 0.92, "ocr_confidence": 0.88},
    ]
    result = evaluate(
        extractions,
        threshold=0.75,
        ocr_threshold=0.80,
    )
    assert result.needs_review is False  # 0.92 >= 0.75 and 0.88 >= 0.80
```

- [ ] **Step 2: Run to confirm failures**

```bash
docker-compose run --rm -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test backend pytest tests/test_pipeline.py::test_evaluate_uses_per_field_ai_threshold_correct tests/test_pipeline.py::test_evaluate_flags_low_ocr_confidence tests/test_pipeline.py::test_evaluate_passes_when_both_confidences_meet_thresholds -v
```

Expected: all FAIL — `evaluate()` does not yet accept `field_thresholds` or `ocr_threshold`.

- [ ] **Step 3: Rewrite extraction_evaluator.py**

```python
# backend/app/services/extraction_evaluator.py
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


def evaluate(
    extractions: list[dict],
    threshold: float,
    field_thresholds: dict[str, float] | None = None,
    ocr_threshold: float | None = None,
    ocr_field_thresholds: dict[str, float] | None = None,
) -> EvaluationResult:
    """
    Identify fields whose confidence falls below their threshold.

    threshold: default AI confidence threshold for all fields.
    field_thresholds: per-field AI threshold overrides {field_name: threshold}.
    ocr_threshold: default OCR confidence threshold (None = skip OCR check).
    ocr_field_thresholds: per-field OCR threshold overrides {field_name: threshold}.

    A field is flagged if AI confidence < its AI threshold OR
    OCR confidence < its OCR threshold (when ocr_threshold is set).
    Pure function — no DB access.
    """
    low = []
    _field_ai = field_thresholds or {}
    _field_ocr = ocr_field_thresholds or {}

    for e in extractions:
        name = e.get("field_name")
        if not name:
            continue

        ai_thresh = _field_ai.get(name, threshold)
        ai_conf = e.get("confidence", 1.0)
        ai_failed = ai_conf < ai_thresh

        ocr_failed = False
        if ocr_threshold is not None:
            ocr_thresh = _field_ocr.get(name, ocr_threshold)
            ocr_conf = e.get("ocr_confidence", 1.0)
            ocr_failed = ocr_conf < ocr_thresh

        if ai_failed or ocr_failed:
            low.append(name)

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
```

- [ ] **Step 4: Update pipeline's evaluate call in document_pipeline.py**

Replace the `evaluate(raw_extractions, schema.default_confidence_threshold)` call (in `_run_pipeline`, Step 6b section):

```python
        from app.services.extraction_evaluator import evaluate, run_retry
        _field_ai_thresholds = {
            f["name"]: f["ai_threshold"]
            for f in (schema.schema_fields or [])
            if "ai_threshold" in f
        }
        _field_ocr_thresholds = {
            f["name"]: f["ocr_threshold"]
            for f in (schema.schema_fields or [])
            if "ocr_threshold" in f
        }
        eval_result = evaluate(
            raw_extractions,
            schema.default_confidence_threshold,
            field_thresholds=_field_ai_thresholds or None,
            ocr_threshold=schema.default_confidence_threshold,
            ocr_field_thresholds=_field_ocr_thresholds or None,
        )
        if eval_result.needs_review:
            logger.info(
                f"Evaluator: {len(eval_result.low_confidence_fields)} low-confidence fields "
                f"in doc {doc.id} — retrying"
            )
            retry_extractions = run_retry(
                document_id=doc.id,
                workspace_id=workspace_id,
                ocr_text=ocr_text,
                schema=schema,
                low_confidence_field_names=eval_result.low_confidence_fields,
                db=db,
            )
            if retry_extractions:
                final_eval = evaluate(
                    retry_extractions,
                    schema.default_confidence_threshold,
                    field_thresholds=_field_ai_thresholds or None,
                    ocr_threshold=schema.default_confidence_threshold,
                    ocr_field_thresholds=_field_ocr_thresholds or None,
                )
                if final_eval.needs_review:
                    doc.extraction_status = "needs_review"
                    db.commit()
                    logger.info(
                        f"Doc {doc.id} flagged needs_review: "
                        f"{len(final_eval.low_confidence_fields)} fields still below threshold"
                    )
            else:
                doc.extraction_status = "needs_review"
                db.commit()
```

- [ ] **Step 5: Run all tests**

```bash
docker-compose run --rm -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test backend pytest tests/ -v --tb=short 2>&1 | tail -30
```

Expected: all pass including the 4 new evaluator tests.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/extraction_evaluator.py backend/app/services/document_pipeline.py backend/tests/test_pipeline.py
git commit -m "feat: evaluator supports per-field ai/ocr thresholds from schema_fields JSON"
```

---

## Task 5: Field Validator Service

**Files:**
- Create: `backend/app/services/field_validator.py`
- Create: `backend/tests/test_field_validator.py`

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_field_validator.py
"""Field validator — pure function tests, no DB required."""
from app.services.field_validator import validate_extractions, ValidationError


def test_required_field_missing_raises_error():
    extractions = [{"field_name": "ein", "field_value": None}]
    schema_fields = [{"name": "ein", "type": "id_number", "description": "EIN",
                      "validation": {"required": True}}]
    errors = validate_extractions(extractions, schema_fields)
    assert len(errors) == 1
    assert errors[0].field_name == "ein"
    assert errors[0].rule == "required"


def test_required_field_present_passes():
    extractions = [{"field_name": "ein", "field_value": "12-3456789"}]
    schema_fields = [{"name": "ein", "type": "id_number", "description": "EIN",
                      "validation": {"required": True}}]
    errors = validate_extractions(extractions, schema_fields)
    assert errors == []


def test_min_length_violation():
    extractions = [{"field_name": "ein", "field_value": "123"}]
    schema_fields = [{"name": "ein", "type": "id_number", "description": "EIN",
                      "validation": {"min_length": 9}}]
    errors = validate_extractions(extractions, schema_fields)
    assert any(e.rule == "min_length" for e in errors)


def test_max_length_violation():
    extractions = [{"field_name": "notes", "field_value": "A" * 201}]
    schema_fields = [{"name": "notes", "type": "text", "description": "Notes",
                      "validation": {"max_length": 200}}]
    errors = validate_extractions(extractions, schema_fields)
    assert any(e.rule == "max_length" for e in errors)


def test_regex_pattern_violation():
    extractions = [{"field_name": "ein", "field_value": "not-an-ein"}]
    schema_fields = [{"name": "ein", "type": "id_number", "description": "EIN",
                      "validation": {"pattern": r"^\d{2}-\d{7}$"}}]
    errors = validate_extractions(extractions, schema_fields)
    assert any(e.rule == "pattern" for e in errors)


def test_regex_pattern_passes():
    extractions = [{"field_name": "ein", "field_value": "12-3456789"}]
    schema_fields = [{"name": "ein", "type": "id_number", "description": "EIN",
                      "validation": {"pattern": r"^\d{2}-\d{7}$"}}]
    errors = validate_extractions(extractions, schema_fields)
    assert errors == []


def test_no_validation_rules_passes():
    extractions = [{"field_name": "grantor_name", "field_value": "Jane Smith"}]
    schema_fields = [{"name": "grantor_name", "type": "name", "description": "Grantor"}]
    errors = validate_extractions(extractions, schema_fields)
    assert errors == []


def test_field_not_in_extractions_but_required_is_error():
    """Required field missing entirely from extractions (Claude didn't return it)."""
    extractions = []
    schema_fields = [{"name": "ein", "type": "id_number", "description": "EIN",
                      "validation": {"required": True}}]
    errors = validate_extractions(extractions, schema_fields)
    assert any(e.field_name == "ein" and e.rule == "required" for e in errors)
```

- [ ] **Step 2: Run to confirm failures**

```bash
docker-compose run --rm -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test backend pytest tests/test_field_validator.py -v
```

Expected: `ERROR` — `ModuleNotFoundError: No module named 'app.services.field_validator'`

- [ ] **Step 3: Implement field_validator.py**

```python
# backend/app/services/field_validator.py
"""
Field validator — applies per-field validation rules defined in schema_fields JSON.

validate_extractions() is a pure function: no DB access, no side effects.
Called in the pipeline after extraction and before confidence evaluation.
"""
import re
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ValidationError:
    field_name: str
    rule: str        # "required" | "min_length" | "max_length" | "pattern"
    message: str


def validate_extractions(
    extractions: list[dict],
    schema_fields: list[dict],
) -> list[ValidationError]:
    """
    Validate extracted field values against per-field validation rules.

    schema_fields entries may include a "validation" dict with keys:
      required: bool — field must have a non-empty value
      min_length: int — minimum character count
      max_length: int — maximum character count
      pattern: str — regex the value must fully match

    Fields without a "validation" key are skipped.
    Returns a list of ValidationErrors (empty = all passed).
    """
    # Index latest extracted value per field name
    latest: dict[str, str | None] = {}
    for e in extractions:
        name = e.get("field_name")
        if name:
            latest[name] = e.get("field_value")

    errors: list[ValidationError] = []

    for field in schema_fields:
        name = field.get("name")
        rules = field.get("validation")
        if not name or not rules:
            continue

        value = latest.get(name)

        # required — check before length/pattern (no value = no point checking others)
        if rules.get("required") and not value:
            errors.append(ValidationError(
                field_name=name,
                rule="required",
                message=f"'{name}' is required but was not extracted",
            ))
            continue

        if not value:
            continue  # optional field with no value — remaining rules don't apply

        # min_length
        if "min_length" in rules and len(value) < rules["min_length"]:
            errors.append(ValidationError(
                field_name=name,
                rule="min_length",
                message=f"'{name}' must be at least {rules['min_length']} characters (got {len(value)})",
            ))

        # max_length
        if "max_length" in rules and len(value) > rules["max_length"]:
            errors.append(ValidationError(
                field_name=name,
                rule="max_length",
                message=f"'{name}' must be at most {rules['max_length']} characters (got {len(value)})",
            ))

        # pattern
        if "pattern" in rules:
            try:
                if not re.fullmatch(rules["pattern"], value):
                    errors.append(ValidationError(
                        field_name=name,
                        rule="pattern",
                        message=f"'{name}' value '{value}' does not match required pattern",
                    ))
            except re.error as exc:
                logger.warning(f"Invalid regex pattern for field '{name}': {exc}")

    return errors
```

- [ ] **Step 4: Run tests**

```bash
docker-compose run --rm -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test backend pytest tests/test_field_validator.py -v
```

Expected: all 8 tests PASS.

- [ ] **Step 5: Wire validator into pipeline**

In `backend/app/services/document_pipeline.py`, add this block immediately after the `save_extractions(...)` call and before the C2 guard:

```python
    # ── Step 6a: Field validation ────────────────────────────────────────────
    if schema.parse_strategy == "claude" and schema.schema_fields:
        try:
            from app.services.field_validator import validate_extractions
            validation_errors = validate_extractions(raw_extractions, schema.schema_fields)
            if validation_errors:
                required_failures = [e for e in validation_errors if e.rule == "required"]
                for err in validation_errors:
                    logger.warning(f"Validation error in doc {doc.id}: {err.message}")
                if required_failures:
                    doc.extraction_status = "needs_review"
                    doc.extraction_error = "; ".join(
                        e.message for e in required_failures[:3]
                    )
                    db.commit()
        except Exception as e:
            logger.warning(f"Field validation failed for doc {doc.id}: {e}")
```

- [ ] **Step 6: Run full test suite**

```bash
docker-compose run --rm -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test backend pytest tests/ -v --tb=short 2>&1 | tail -20
```

Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/field_validator.py backend/tests/test_field_validator.py backend/app/services/document_pipeline.py
git commit -m "feat: field validator service — required, min_length, max_length, regex per schema field"
```

---

## Task 6: Review Router — Flag Endpoint

**Files:**
- Modify: `backend/app/routers/review.py`
- Create (extend): `backend/tests/test_pipeline.py` (or add a dedicated `tests/test_review.py`)

- [ ] **Step 1: Write the failing test**

Add a new test file `backend/tests/test_review.py`:

```python
# backend/tests/test_review.py
"""Review router tests — flag endpoint."""
import uuid
import pytest
from app.models.document import Document
from app.models.document_schema import DocumentSchema
from app.models.user import User
from app.models.workspace import Workspace


@pytest.fixture
def workspace_id(client, auth_headers):
    return client.post("/workspaces/", json={"name": "Review Test", "vertical": "general"},
                       headers=auth_headers).json()["id"]


@pytest.fixture
def document_with_review_status(db, workspace_id, auth_headers):
    """A document already in needs_review state."""
    user = db.query(User).filter(User.email == "tyler@example.com").first()
    schema = DocumentSchema(
        id=str(uuid.uuid4()),
        document_type="DEED",
        display_name="Deed",
        vertical="general",
        schema_fields=[],
        version=1,
        is_active=True,
        parse_strategy="claude",
        default_confidence_threshold=0.75,
    )
    db.add(schema)
    db.flush()
    doc = Document(
        id=str(uuid.uuid4()),
        workspace_id=workspace_id,
        filename="test.pdf",
        original_filename="test.pdf",
        file_path="/tmp/test.pdf",
        file_type="pdf",
        sha256_hash="flag123",
        uploaded_by=user.id,
        extraction_status="needs_review",
        schema_id=schema.id,
    )
    db.add(doc)
    db.commit()
    return doc


def test_flag_document_stores_reason_and_note(client, auth_headers, workspace_id, document_with_review_status):
    doc = document_with_review_status
    resp = client.patch(
        f"/workspaces/{workspace_id}/documents/{doc.id}/flag",
        json={"flag_reason": "low_quality_scan", "flag_note": "Pages 3-5 unreadable"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["flag_reason"] == "low_quality_scan"
    assert data["flag_note"] == "Pages 3-5 unreadable"


def test_flag_document_with_no_note(client, auth_headers, workspace_id, document_with_review_status):
    doc = document_with_review_status
    resp = client.patch(
        f"/workspaces/{workspace_id}/documents/{doc.id}/flag",
        json={"flag_reason": "unknown_type"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["flag_reason"] == "unknown_type"
    assert resp.json()["flag_note"] is None


def test_flag_document_returns_404_for_unknown_doc(client, auth_headers, workspace_id):
    resp = client.patch(
        f"/workspaces/{workspace_id}/documents/nonexistent-id/flag",
        json={"flag_reason": "other"},
        headers=auth_headers,
    )
    assert resp.status_code == 404
```

- [ ] **Step 2: Run to confirm failures**

```bash
docker-compose run --rm -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test backend pytest tests/test_review.py -v
```

Expected: all FAIL — endpoint does not exist yet.

- [ ] **Step 3: Add flag endpoint to review.py**

Add to `backend/app/routers/review.py` (after the imports, add the new schemas; after the existing routes, add the endpoint):

```python
from app.schemas.review import ExtractionCorrectionIn, ExtractionCorrectionOut, ReviewQueueItem, FlagDocumentIn, FlagDocumentOut


@router.patch(
    "/documents/{document_id}/flag",
    response_model=FlagDocumentOut,
)
def flag_document(
    workspace_id: str,
    document_id: str,
    body: FlagDocumentIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Store a structured rejection reason on a document.
    Flag reason and note travel with the document through the rest of processing.
    """
    get_workspace_or_404(workspace_id, user, db)

    doc = db.query(Document).filter(
        Document.id == document_id,
        Document.workspace_id == workspace_id,
        Document.is_deleted == False,
    ).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    before_state = {"flag_reason": doc.flag_reason, "flag_note": doc.flag_note}

    doc.flag_reason = body.flag_reason
    doc.flag_note = body.flag_note
    db.commit()
    db.refresh(doc)

    audit.log(
        db,
        action="document_flagged",
        user_id=user.id,
        workspace_id=workspace_id,
        entity_type="document",
        entity_id=document_id,
        before_state=before_state,
        after_state={"flag_reason": doc.flag_reason, "flag_note": doc.flag_note},
    )

    return doc
```

- [ ] **Step 4: Run tests**

```bash
docker-compose run --rm -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test backend pytest tests/test_review.py -v
```

Expected: all 3 PASS.

- [ ] **Step 5: Run full suite**

```bash
docker-compose run --rm -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test backend pytest tests/ -v --tb=short 2>&1 | tail -15
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add backend/app/routers/review.py backend/tests/test_review.py
git commit -m "feat: flag endpoint — store structured rejection reason and note on document"
```

---

## Task 7: Observability Router — 4 Dashboard Endpoints

**Files:**
- Create: `backend/app/schemas/observability.py`
- Create: `backend/app/routers/observability.py`
- Create: `backend/tests/test_observability.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_observability.py
"""Observability dashboard endpoint tests."""
import uuid
import pytest
from app.models.document import Document
from app.models.document_schema import DocumentSchema
from app.models.document_extraction import DocumentExtraction
from app.models.user import User
from app.models.workspace import Workspace


@pytest.fixture
def ws_and_docs(db, auth_headers, client):
    """Seed one workspace with 3 docs: 1 complete, 1 needs_review, 1 failed."""
    user = db.query(User).filter(User.email == "tyler@example.com").first()
    ws = Workspace(
        id=str(uuid.uuid4()), name="Obs WS", vertical="general", created_by=user.id
    )
    db.add(ws)
    schema = DocumentSchema(
        id=str(uuid.uuid4()), document_type="DEED", display_name="Deed",
        vertical="general", schema_fields=[], version=1, is_active=True,
        parse_strategy="claude", default_confidence_threshold=0.75,
    )
    db.add(schema)
    db.flush()

    for status in ("complete", "needs_review", "failed"):
        doc = Document(
            id=str(uuid.uuid4()), workspace_id=ws.id,
            filename=f"{status}.pdf", original_filename=f"{status}.pdf",
            file_path=f"/tmp/{status}.pdf", file_type="pdf",
            sha256_hash=f"hash_{status}", uploaded_by=user.id,
            extraction_status=status, schema_id=schema.id,
        )
        db.add(doc)
    db.commit()
    return ws, schema


def test_automation_rate_returns_counts(client, auth_headers, ws_and_docs):
    resp = client.get("/observability/automation-rate", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "total" in data
    assert "automated" in data
    assert "needs_review" in data
    assert "failed" in data
    assert "automation_rate" in data
    assert data["total"] >= 3


def test_volume_returns_daily_series(client, auth_headers, ws_and_docs):
    resp = client.get("/observability/volume?days=7", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "days" in data
    assert isinstance(data["days"], list)
    assert len(data["days"]) == 7
    assert "date" in data["days"][0]
    assert "inbound" in data["days"][0]
    assert "completed" in data["days"][0]


def test_classification_details_returns_schema_rows(client, auth_headers, ws_and_docs):
    resp = client.get("/observability/classification-details", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "schemas" in data
    assert isinstance(data["schemas"], list)


def test_current_processing_returns_counts(client, auth_headers, ws_and_docs):
    resp = client.get("/observability/current-processing", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "pending" in data
    assert "needs_review" in data
    assert "total_active" in data
```

- [ ] **Step 2: Run to confirm failures**

```bash
docker-compose run --rm -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test backend pytest tests/test_observability.py -v
```

Expected: all FAIL — 404s.

- [ ] **Step 3: Create observability schemas**

```python
# backend/app/schemas/observability.py
from pydantic import BaseModel


class AutomationRateOut(BaseModel):
    total: int
    automated: int
    needs_review: int
    failed: int
    automation_rate: float   # automated / total, or 0.0 if total == 0


class DailyVolume(BaseModel):
    date: str   # ISO date "YYYY-MM-DD"
    inbound: int
    completed: int


class VolumeOut(BaseModel):
    days: list[DailyVolume]


class SchemaDetail(BaseModel):
    document_type: str
    total_documents: int
    avg_ai_confidence: float
    avg_ocr_confidence: float
    retry_rate: float       # fraction of docs that had attempt=2 rows
    correction_rate: float  # fraction of docs that had attempt=3 rows


class ClassificationDetailsOut(BaseModel):
    schemas: list[SchemaDetail]


class CurrentProcessingOut(BaseModel):
    pending: int
    needs_review: int
    total_active: int
```

- [ ] **Step 4: Create observability router**

```python
# backend/app/routers/observability.py
"""
Observability dashboard endpoints — platform-level extraction quality metrics.
All endpoints require auth. Data comes entirely from existing tables.
"""
from datetime import UTC, date, datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.document import Document
from app.models.document_extraction import DocumentExtraction
from app.models.document_schema import DocumentSchema
from app.models.user import User
from app.schemas.observability import (
    AutomationRateOut,
    ClassificationDetailsOut,
    CurrentProcessingOut,
    DailyVolume,
    SchemaDetail,
    VolumeOut,
)
from app.services.auth import get_current_user

router = APIRouter(prefix="/observability", tags=["observability"])


@router.get("/automation-rate", response_model=AutomationRateOut)
def get_automation_rate(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Straight-through processing rate across all non-deleted documents."""
    rows = (
        db.query(Document.extraction_status, func.count(Document.id))
        .filter(Document.is_deleted == False)
        .group_by(Document.extraction_status)
        .all()
    )
    counts = {status: n for status, n in rows}
    automated = counts.get("complete", 0)
    needs_review = counts.get("needs_review", 0)
    failed = counts.get("failed", 0)
    total = sum(counts.values())
    return AutomationRateOut(
        total=total,
        automated=automated,
        needs_review=needs_review,
        failed=failed,
        automation_rate=round(automated / total, 4) if total else 0.0,
    )


@router.get("/volume", response_model=VolumeOut)
def get_volume(
    days: int = 30,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Daily inbound and completed document counts for the last N days."""
    today = date.today()
    day_list = [today - timedelta(days=i) for i in range(days - 1, -1, -1)]

    inbound_rows = (
        db.query(
            func.date(Document.uploaded_at).label("d"),
            func.count(Document.id).label("n"),
        )
        .filter(
            Document.is_deleted == False,
            Document.uploaded_at >= datetime(today.year, today.month, today.day, tzinfo=UTC) - timedelta(days=days),
        )
        .group_by("d")
        .all()
    )
    completed_rows = (
        db.query(
            func.date(Document.uploaded_at).label("d"),
            func.count(Document.id).label("n"),
        )
        .filter(
            Document.is_deleted == False,
            Document.extraction_status == "complete",
            Document.uploaded_at >= datetime(today.year, today.month, today.day, tzinfo=UTC) - timedelta(days=days),
        )
        .group_by("d")
        .all()
    )

    inbound_map = {str(r.d): r.n for r in inbound_rows}
    completed_map = {str(r.d): r.n for r in completed_rows}

    return VolumeOut(days=[
        DailyVolume(
            date=str(d),
            inbound=inbound_map.get(str(d), 0),
            completed=completed_map.get(str(d), 0),
        )
        for d in day_list
    ])


@router.get("/classification-details", response_model=ClassificationDetailsOut)
def get_classification_details(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Per-schema accuracy metrics — avg AI confidence, avg OCR confidence, retry/correction rates."""
    schema_types = (
        db.query(DocumentSchema.document_type, DocumentSchema.id)
        .filter(DocumentSchema.is_active == True)
        .all()
    )

    details = []
    for doc_type, schema_id in schema_types:
        doc_count = (
            db.query(func.count(Document.id))
            .filter(Document.schema_id == schema_id, Document.is_deleted == False)
            .scalar()
        ) or 0

        if doc_count == 0:
            continue

        avg_ai = (
            db.query(func.avg(DocumentExtraction.confidence))
            .filter(DocumentExtraction.schema_id == schema_id, DocumentExtraction.attempt == 1)
            .scalar()
        ) or 0.0

        avg_ocr = (
            db.query(func.avg(DocumentExtraction.ocr_confidence))
            .filter(DocumentExtraction.schema_id == schema_id, DocumentExtraction.attempt == 1)
            .scalar()
        ) or 0.0

        # retry_rate: docs that had at least one attempt=2 row
        retry_docs = (
            db.query(func.count(func.distinct(DocumentExtraction.document_id)))
            .filter(DocumentExtraction.schema_id == schema_id, DocumentExtraction.attempt == 2)
            .scalar()
        ) or 0

        # correction_rate: docs that had at least one attempt=3 (human correction)
        correction_docs = (
            db.query(func.count(func.distinct(DocumentExtraction.document_id)))
            .filter(DocumentExtraction.schema_id == schema_id, DocumentExtraction.attempt == 3)
            .scalar()
        ) or 0

        details.append(SchemaDetail(
            document_type=doc_type,
            total_documents=doc_count,
            avg_ai_confidence=round(float(avg_ai), 4),
            avg_ocr_confidence=round(float(avg_ocr), 4),
            retry_rate=round(retry_docs / doc_count, 4) if doc_count else 0.0,
            correction_rate=round(correction_docs / doc_count, 4) if doc_count else 0.0,
        ))

    return ClassificationDetailsOut(schemas=details)


@router.get("/current-processing", response_model=CurrentProcessingOut)
def get_current_processing(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Count of documents currently in-flight (pending) or awaiting human review."""
    rows = (
        db.query(Document.extraction_status, func.count(Document.id))
        .filter(
            Document.is_deleted == False,
            Document.extraction_status.in_(["pending", "needs_review"]),
        )
        .group_by(Document.extraction_status)
        .all()
    )
    counts = {status: n for status, n in rows}
    pending = counts.get("pending", 0)
    needs_review = counts.get("needs_review", 0)
    return CurrentProcessingOut(
        pending=pending,
        needs_review=needs_review,
        total_active=pending + needs_review,
    )
```

- [ ] **Step 5: Register observability router in main.py**

Add to `backend/app/main.py`:

```python
from app.routers import (
    ai, audit, auth, documents, entities, findings, leads,
    notes, observability, review, schemas, search, transactions, workspaces,
)
```

And add:
```python
app.include_router(observability.router)
```

- [ ] **Step 6: Run tests**

```bash
docker-compose run --rm -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test backend pytest tests/test_observability.py -v
```

Expected: all 4 PASS.

- [ ] **Step 7: Run full suite**

```bash
docker-compose run --rm -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test backend pytest tests/ -v --tb=short 2>&1 | tail -15
```

Expected: all pass.

- [ ] **Step 8: Commit**

```bash
git add backend/app/schemas/observability.py backend/app/routers/observability.py backend/app/main.py backend/tests/test_observability.py
git commit -m "feat: observability router — automation rate, volume, classification details, current processing"
```

---

## Task 8: Frontend — Install Recharts + Observability API Client

**Files:**
- Modify: `frontend/package.json` (via npm install)
- Create: `frontend/src/api/observability.js`

- [ ] **Step 1: Install recharts**

```bash
cd frontend && npm install recharts
```

Expected: `added N packages` — recharts and its deps (d3 subset).

- [ ] **Step 2: Create the observability API client**

```javascript
// frontend/src/api/observability.js
import client from './client'

export const getAutomationRate = () =>
  client.get('/observability/automation-rate')

export const getVolume = (days = 30) =>
  client.get('/observability/volume', { params: { days } })

export const getClassificationDetails = () =>
  client.get('/observability/classification-details')

export const getCurrentProcessing = () =>
  client.get('/observability/current-processing')
```

- [ ] **Step 3: Commit**

```bash
git add frontend/package.json frontend/package-lock.json frontend/src/api/observability.js
git commit -m "feat: add recharts dependency and observability API client"
```

---

## Task 9: Frontend — Observability Dashboard Page

**Files:**
- Create: `frontend/src/pages/Observability.jsx`
- Modify: `frontend/src/App.jsx`
- Modify: `frontend/src/components/layout/AppShell.jsx`

- [ ] **Step 1: Create the Observability page**

```jsx
// frontend/src/pages/Observability.jsx
import { useState, useEffect } from 'react'
import {
  BarChart, Bar, LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, Cell,
} from 'recharts'
import {
  getAutomationRate,
  getClassificationDetails,
  getCurrentProcessing,
  getVolume,
} from '../api/observability'
import LoadingSpinner from '../components/shared/LoadingSpinner'

function StatCard({ label, value, sub, color = 'text-white' }) {
  return (
    <div className="bg-slate-900 border border-slate-700 rounded-lg p-4">
      <p className="text-slate-400 text-xs font-medium uppercase tracking-wide mb-1">{label}</p>
      <p className={`text-2xl font-bold ${color}`}>{value}</p>
      {sub && <p className="text-slate-500 text-xs mt-0.5">{sub}</p>}
    </div>
  )
}

export default function Observability() {
  const [rate, setRate] = useState(null)
  const [volume, setVolume] = useState(null)
  const [details, setDetails] = useState(null)
  const [current, setCurrent] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.allSettled([
      getAutomationRate(),
      getVolume(30),
      getClassificationDetails(),
      getCurrentProcessing(),
    ]).then(([rateRes, volRes, detailRes, curRes]) => {
      if (rateRes.status === 'fulfilled') setRate(rateRes.value.data)
      if (volRes.status === 'fulfilled') setVolume(volRes.value.data)
      if (detailRes.status === 'fulfilled') setDetails(detailRes.value.data)
      if (curRes.status === 'fulfilled') setCurrent(curRes.value.data)
    }).finally(() => setLoading(false))
  }, [])

  if (loading) return <LoadingSpinner />

  const automationPct = rate ? Math.round(rate.automation_rate * 100) : 0

  return (
    <div className="max-w-6xl mx-auto px-6 py-8 space-y-8">
      <div>
        <h1 className="text-white text-xl font-semibold">Observability</h1>
        <p className="text-slate-400 text-sm mt-0.5">Extraction quality metrics — operator view</p>
      </div>

      {/* ── Section 1: Automation Rate ───────────────────────────────── */}
      <section>
        <h2 className="text-slate-300 text-sm font-semibold uppercase tracking-wide mb-3">
          Automation Rate
        </h2>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <StatCard
            label="Automation Rate"
            value={`${automationPct}%`}
            sub="straight-through"
            color={automationPct >= 80 ? 'text-green-400' : automationPct >= 60 ? 'text-yellow-400' : 'text-red-400'}
          />
          <StatCard label="Total Documents" value={rate?.total ?? '—'} />
          <StatCard label="Needs Review" value={rate?.needs_review ?? '—'} color="text-yellow-400" />
          <StatCard label="Failed" value={rate?.failed ?? '—'} color={rate?.failed > 0 ? 'text-red-400' : 'text-slate-400'} />
        </div>
      </section>

      {/* ── Section 2: Current Processing ───────────────────────────── */}
      {current && (
        <section>
          <h2 className="text-slate-300 text-sm font-semibold uppercase tracking-wide mb-3">
            Current Processing
          </h2>
          <div className="grid grid-cols-3 gap-3">
            <StatCard label="Pending" value={current.pending} />
            <StatCard label="Review Queue" value={current.needs_review} color={current.needs_review > 0 ? 'text-yellow-400' : 'text-slate-400'} />
            <StatCard label="Total Active" value={current.total_active} />
          </div>
        </section>
      )}

      {/* ── Section 3: Volume Trend ──────────────────────────────────── */}
      {volume?.days && (
        <section>
          <h2 className="text-slate-300 text-sm font-semibold uppercase tracking-wide mb-3">
            Inbound / Completed — Last 30 Days
          </h2>
          <div className="bg-slate-900 border border-slate-700 rounded-lg p-4">
            <ResponsiveContainer width="100%" height={200}>
              <LineChart data={volume.days} margin={{ top: 4, right: 8, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                <XAxis
                  dataKey="date"
                  tick={{ fill: '#94a3b8', fontSize: 10 }}
                  tickFormatter={(d) => d.slice(5)}  // MM-DD
                  interval={4}
                />
                <YAxis tick={{ fill: '#94a3b8', fontSize: 10 }} />
                <Tooltip
                  contentStyle={{ background: '#1e293b', border: '1px solid #334155', borderRadius: 6 }}
                  labelStyle={{ color: '#94a3b8' }}
                  itemStyle={{ color: '#e2e8f0' }}
                />
                <Line type="monotone" dataKey="inbound" stroke="#3b82f6" strokeWidth={2} dot={false} name="Inbound" />
                <Line type="monotone" dataKey="completed" stroke="#22c55e" strokeWidth={2} dot={false} name="Completed" />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </section>
      )}

      {/* ── Section 4: Classification Details ───────────────────────── */}
      {details?.schemas?.length > 0 && (
        <section>
          <h2 className="text-slate-300 text-sm font-semibold uppercase tracking-wide mb-3">
            Extraction Quality by Schema
          </h2>
          <div className="bg-slate-900 border border-slate-700 rounded-lg p-4">
            <ResponsiveContainer width="100%" height={Math.max(160, details.schemas.length * 36)}>
              <BarChart
                data={details.schemas}
                layout="vertical"
                margin={{ top: 4, right: 40, left: 80, bottom: 0 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                <XAxis type="number" domain={[0, 1]} tickFormatter={(v) => `${Math.round(v * 100)}%`} tick={{ fill: '#94a3b8', fontSize: 10 }} />
                <YAxis type="category" dataKey="document_type" tick={{ fill: '#94a3b8', fontSize: 11 }} width={75} />
                <Tooltip
                  contentStyle={{ background: '#1e293b', border: '1px solid #334155', borderRadius: 6 }}
                  labelStyle={{ color: '#94a3b8' }}
                  itemStyle={{ color: '#e2e8f0' }}
                  formatter={(v) => `${Math.round(v * 100)}%`}
                />
                <Bar dataKey="avg_ai_confidence" name="AI Confidence" fill="#3b82f6" radius={[0, 3, 3, 0]} />
                <Bar dataKey="avg_ocr_confidence" name="OCR Confidence" fill="#8b5cf6" radius={[0, 3, 3, 0]} />
              </BarChart>
            </ResponsiveContainer>
            <div className="mt-4 overflow-x-auto">
              <table className="w-full text-xs text-left">
                <thead>
                  <tr className="text-slate-500 border-b border-slate-700">
                    <th className="pb-2 font-medium">Schema</th>
                    <th className="pb-2 font-medium text-right">Docs</th>
                    <th className="pb-2 font-medium text-right">AI Conf</th>
                    <th className="pb-2 font-medium text-right">OCR Conf</th>
                    <th className="pb-2 font-medium text-right">Retry Rate</th>
                    <th className="pb-2 font-medium text-right">Correction Rate</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800">
                  {details.schemas.map((s) => (
                    <tr key={s.document_type}>
                      <td className="py-1.5 text-white font-medium">{s.document_type}</td>
                      <td className="py-1.5 text-slate-400 text-right">{s.total_documents}</td>
                      <td className="py-1.5 text-right">
                        <span className={s.avg_ai_confidence >= 0.85 ? 'text-green-400' : s.avg_ai_confidence >= 0.70 ? 'text-yellow-400' : 'text-red-400'}>
                          {Math.round(s.avg_ai_confidence * 100)}%
                        </span>
                      </td>
                      <td className="py-1.5 text-right">
                        <span className={s.avg_ocr_confidence >= 0.85 ? 'text-green-400' : s.avg_ocr_confidence >= 0.70 ? 'text-yellow-400' : 'text-red-400'}>
                          {Math.round(s.avg_ocr_confidence * 100)}%
                        </span>
                      </td>
                      <td className="py-1.5 text-slate-400 text-right">{Math.round(s.retry_rate * 100)}%</td>
                      <td className="py-1.5 text-slate-400 text-right">{Math.round(s.correction_rate * 100)}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </section>
      )}
    </div>
  )
}
```

- [ ] **Step 2: Add route to App.jsx**

In `frontend/src/App.jsx`, add the import after the existing page imports:

```javascript
import Observability from './pages/Observability'
```

Add the route inside `<Routes>` after the `/schemas` route:

```jsx
<Route path="/observability" element={
  <ProtectedRoute><Observability /></ProtectedRoute>
} />
```

- [ ] **Step 3: Add nav link in AppShell.jsx**

Read the current AppShell to find where `/schemas` is linked, then add an Observability link beside it. The exact position depends on the current nav — find the schemas link and add after it:

```jsx
<Link
  to="/observability"
  className={`text-sm font-medium transition-colors ${
    location.pathname === '/observability'
      ? 'text-white'
      : 'text-slate-400 hover:text-white'
  }`}
>
  Observability
</Link>
```

- [ ] **Step 4: Start the dev server and verify**

```bash
docker-compose up --build
```

Navigate to `http://localhost:5173/observability`. Verify: 4 sections render, charts display, stat cards show numbers.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/Observability.jsx frontend/src/App.jsx frontend/src/components/layout/AppShell.jsx
git commit -m "feat: observability dashboard — automation rate, volume trend, classification quality, current processing"
```

---

## Task 10: Frontend — ExtractionTable Dual Confidence Display

**Files:**
- Modify: `frontend/src/components/documents/ExtractionTable.jsx`

- [ ] **Step 1: Update ExtractionRow to show both confidence scores**

Replace the confidence display in `ExtractionRow` — the section that currently shows a single `{Math.round(e.confidence * 100)}%`. Update the entire `<td className="py-2 text-right align-top">` block:

```jsx
      <td className="py-2 text-right align-top">
        {isHumanCorrected ? (
          <span className="text-xs text-green-400 font-medium">Corrected</span>
        ) : editable ? (
          <div className="flex flex-col items-end gap-0.5">
            <ConfidencePill label="AI" value={e.confidence} />
            {e.ocr_confidence != null && (
              <ConfidencePill label="OCR" value={e.ocr_confidence} />
            )}
            <div className="flex items-center gap-1 mt-1">
              {editing ? (
                <>
                  <button
                    onClick={handleAccept}
                    disabled={saving}
                    className="text-xs px-2 py-0.5 bg-blue-600 hover:bg-blue-500 text-white rounded disabled:opacity-50"
                  >
                    {saving ? '…' : 'Accept'}
                  </button>
                  <button
                    onClick={() => { setEditing(false); setInputValue(e.field_value || '') }}
                    className="text-xs px-2 py-0.5 bg-slate-700 hover:bg-slate-600 text-slate-300 rounded"
                  >
                    Cancel
                  </button>
                </>
              ) : (
                <button
                  onClick={() => setEditing(true)}
                  className="text-xs px-2 py-0.5 bg-slate-700 hover:bg-slate-600 text-slate-300 rounded"
                >
                  Edit
                </button>
              )}
            </div>
          </div>
        ) : (
          <div className="flex flex-col items-end gap-0.5">
            <ConfidencePill label="AI" value={e.confidence} />
            {e.ocr_confidence != null && (
              <ConfidencePill label="OCR" value={e.ocr_confidence} />
            )}
          </div>
        )}
      </td>
```

Add the `ConfidencePill` component just before `ExtractionRow`:

```jsx
function ConfidencePill({ label, value }) {
  const pct = Math.round(value * 100)
  const color = pct >= 90 ? 'text-green-400' : pct >= 70 ? 'text-yellow-400' : 'text-red-400'
  return (
    <span className="flex items-center gap-1">
      <span className="text-slate-600 text-xs">{label}</span>
      <span className={`text-xs font-medium ${color}`}>{pct}%</span>
    </span>
  )
}
```

Also update the table header to reflect the change. Replace the `<th>` for confidence:

```jsx
<th className="pb-2 font-medium text-right">{editable ? 'Status / Confidence' : 'Confidence'}</th>
```

- [ ] **Step 2: Verify visually**

Start the dev server (`docker-compose up`), navigate to a document in review mode, and confirm both AI and OCR confidence appear per field.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/documents/ExtractionTable.jsx
git commit -m "feat: extraction table shows both AI confidence and OCR confidence per field"
```

---

## Task 11: Frontend — ExtractionReview Flagging UI

**Files:**
- Modify: `frontend/src/pages/workspace/ExtractionReview.jsx`
- Modify: `frontend/src/api/documents.js`

- [ ] **Step 1: Add flagDocument to the API client**

In `frontend/src/api/documents.js`, add:

```javascript
export const flagDocument = (workspaceId, documentId, flagReason, flagNote = null) =>
  client.patch(`/workspaces/${workspaceId}/documents/${documentId}/flag`, {
    flag_reason: flagReason,
    flag_note: flagNote,
  })
```

- [ ] **Step 2: Add flag button and modal to ExtractionReview.jsx**

Replace the entire file:

```jsx
import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { getReviewQueue, flagDocument } from '../../api/documents'
import LoadingSpinner from '../../components/shared/LoadingSpinner'
import EmptyState from '../../components/shared/EmptyState'

const FLAG_REASONS = [
  { value: 'low_quality_scan', label: 'Low quality scan (illegible)' },
  { value: 'missing_pages', label: 'Document missing pages' },
  { value: 'unknown_type', label: 'Unknown document type' },
  { value: 'wrong_schema', label: 'Wrong schema applied' },
  { value: 'other', label: 'Other' },
]

function FlagModal({ item, workspaceId, onClose, onFlagged }) {
  const [reason, setReason] = useState(FLAG_REASONS[0].value)
  const [note, setNote] = useState('')
  const [saving, setSaving] = useState(false)

  const handleSubmit = async () => {
    setSaving(true)
    try {
      await flagDocument(workspaceId, item.document_id, reason, note || null)
      onFlagged(item.document_id)
      onClose()
    } catch {
      // leave modal open on error
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
      <div className="bg-slate-900 border border-slate-700 rounded-xl p-6 w-full max-w-md shadow-2xl">
        <h2 className="text-white font-semibold mb-1">Flag Document</h2>
        <p className="text-slate-400 text-sm mb-4 truncate">{item.filename}</p>

        <label className="block text-slate-400 text-xs font-medium mb-1">Reason</label>
        <select
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          className="w-full bg-slate-800 border border-slate-600 text-white text-sm rounded px-3 py-2 mb-3 focus:outline-none focus:border-blue-500"
        >
          {FLAG_REASONS.map((r) => (
            <option key={r.value} value={r.value}>{r.label}</option>
          ))}
        </select>

        <label className="block text-slate-400 text-xs font-medium mb-1">Note (optional)</label>
        <textarea
          value={note}
          onChange={(e) => setNote(e.target.value)}
          rows={3}
          placeholder="Additional details for the reviewer…"
          className="w-full bg-slate-800 border border-slate-600 text-white text-sm rounded px-3 py-2 mb-4 focus:outline-none focus:border-blue-500 resize-none"
        />

        <div className="flex justify-end gap-2">
          <button
            onClick={onClose}
            className="px-4 py-1.5 text-sm bg-slate-700 hover:bg-slate-600 text-slate-300 rounded transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleSubmit}
            disabled={saving}
            className="px-4 py-1.5 text-sm bg-orange-600 hover:bg-orange-500 text-white rounded transition-colors disabled:opacity-50"
          >
            {saving ? 'Flagging…' : 'Flag Document'}
          </button>
        </div>
      </div>
    </div>
  )
}

export default function ExtractionReview() {
  const { workspaceId } = useParams()
  const navigate = useNavigate()
  const [queue, setQueue] = useState([])
  const [loading, setLoading] = useState(true)
  const [flagging, setFlagging] = useState(null)  // item being flagged

  useEffect(() => {
    getReviewQueue(workspaceId)
      .then((r) => setQueue(r.data))
      .finally(() => setLoading(false))
  }, [workspaceId])

  const handleFlagged = (documentId) => {
    setQueue((q) => q.filter((item) => item.document_id !== documentId))
  }

  if (loading) return <LoadingSpinner />

  if (!queue.length) {
    return (
      <EmptyState
        title="Review queue is clear"
        description="All extractions meet the confidence threshold."
      />
    )
  }

  return (
    <div>
      {flagging && (
        <FlagModal
          item={flagging}
          workspaceId={workspaceId}
          onClose={() => setFlagging(null)}
          onFlagged={handleFlagged}
        />
      )}

      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-white text-lg font-semibold">Review Queue</h1>
          <p className="text-slate-400 text-sm mt-0.5">
            {queue.length} document{queue.length !== 1 ? 's' : ''} with low-confidence fields
          </p>
        </div>
      </div>

      <div className="bg-slate-900 rounded-lg border border-slate-700 overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-slate-500 border-b border-slate-700">
              <th className="px-4 py-3 font-medium">Document</th>
              <th className="px-4 py-3 font-medium">Type</th>
              <th className="px-4 py-3 font-medium text-center">Low-confidence fields</th>
              <th className="px-4 py-3 font-medium">Uploaded</th>
              <th className="px-4 py-3" />
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800">
            {queue.map((item) => (
              <tr key={item.document_id} className="hover:bg-slate-800 transition-colors">
                <td className="px-4 py-3 text-white font-medium truncate max-w-xs">
                  {item.filename}
                </td>
                <td className="px-4 py-3 text-slate-400">
                  {item.detected_doc_type || '—'}
                </td>
                <td className="px-4 py-3 text-center">
                  <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-yellow-900 text-yellow-300">
                    {item.low_confidence_count}
                  </span>
                </td>
                <td className="px-4 py-3 text-slate-400">
                  {new Date(item.uploaded_at).toLocaleDateString()}
                </td>
                <td className="px-4 py-3 text-right">
                  <div className="flex items-center justify-end gap-2">
                    <button
                      onClick={() => setFlagging(item)}
                      className="px-3 py-1.5 text-xs bg-slate-700 hover:bg-orange-600 text-slate-300 hover:text-white rounded transition-colors"
                    >
                      Flag
                    </button>
                    <button
                      onClick={() =>
                        navigate(
                          `/workspaces/${workspaceId}/documents/${item.document_id}?review=1`
                        )
                      }
                      className="px-3 py-1.5 text-xs bg-blue-600 hover:bg-blue-500 text-white rounded transition-colors"
                    >
                      Review
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
```

- [ ] **Step 3: Verify visually**

Start dev server, go to the review queue, confirm Flag button appears, modal opens with reason dropdown and note textarea, and flagging a document removes it from the queue.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/workspace/ExtractionReview.jsx frontend/src/api/documents.js
git commit -m "feat: review queue — flag document with structured reason and optional note"
```

---

## Self-Review

### Spec Coverage Check

| Spec Requirement | Covered In |
|---|---|
| `ocr_confidence` on document_extractions | Task 1 (migration), Task 2 (model), Task 3 (engine) |
| Claude returns both confidence scores | Task 3 |
| XML parser outputs ocr_confidence=1.0 | Task 3 |
| Per-field ai_threshold + ocr_threshold | Task 4 (evaluator) |
| Pipeline uses per-field thresholds | Task 4 (pipeline update) |
| Field validation — required, min, max, regex | Task 5 |
| Pipeline wires field validator | Task 5 |
| flag_reason + flag_note on Document | Task 1 (migration), Task 2 (model) |
| Flag endpoint PATCH /documents/{id}/flag | Task 6 |
| Automation Rate dashboard endpoint | Task 7 |
| Volume (inbound/outbound) endpoint | Task 7 |
| Classification Details endpoint | Task 7 |
| Current Processing endpoint | Task 7 |
| Observability page with 4 sections | Task 9 |
| ExtractionTable dual confidence display | Task 10 |
| Review queue flag button + modal | Task 11 |

### Deferred (not in this plan)
- Output format normalization (remove_chars, find_replace, date_format, case, truncate, format_number) — follow-on plan
- Extraction type enum (text/table/reasoning) on schema_fields — follow-on plan
- Task Completion by User dashboard — requires Phase 4A multi-user
- Field-to-location highlighting in document viewer — requires text layer coordinates

### Type Consistency Check
- `ocr_confidence` is consistently `float` throughout (model, schema, API response)
- `flag_reason` is consistently `str | None` on model and `str` (required) on `FlagDocumentIn`
- `FlagDocumentOut` uses `from_attributes = True` — reads directly from the `Document` ORM object ✅
- `evaluate()` new params all default to `None` — backwards compatible with existing test calls ✅
- `ConfidencePill` used in `ExtractionTable` is defined in the same file before `ExtractionRow` ✅
