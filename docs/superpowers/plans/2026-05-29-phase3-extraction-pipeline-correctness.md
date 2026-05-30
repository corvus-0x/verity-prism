# Phase 3 — Extraction Pipeline Correctness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close H4 (no pipeline tests), C2 (silent false-`complete` on extraction failure), H5 (4000-char text cap silently truncates evidence), and L3 (orphaned file on pipeline failure).

**Architecture:** Write tests first (H4 TDD baseline), then implement each fix with its tests already in place. A new `test_pipeline.py` file covers `document_pipeline._run_pipeline` and `extraction_engine.extract_fields` end-to-end with mocked Claude. The C2 fix signals extraction failure by raising `ExtractionBatchError` from `_extract_batch` instead of returning `[]`. The H5 fix removes the 4000-char cap. The L3 fix cleans up the stored file in `_fail`.

**Tech Stack:** Python + pytest + `unittest.mock.patch`; FastAPI TestClient; SQLAlchemy direct model creation (same pattern as `test_extractions.py`).

---

## File Map

| File | Action | What changes |
|---|---|---|
| `backend/tests/test_pipeline.py` | **Create** | All new pipeline tests (H4, C2, H5, L3) |
| `backend/app/services/extraction_engine.py` | **Modify** | Add `ExtractionBatchError`; `_extract_batch` raises on failure; `extract_fields` tracks + re-raises; raise `TEXT_LIMIT` from 4000 to 200_000 |
| `backend/app/services/extraction_evaluator.py` | **Modify** | `run_retry` catches `ExtractionBatchError` so retry failure stays non-fatal |
| `backend/app/services/document_pipeline.py` | **Modify** | `_fail` deletes the stored file (L3); pipeline-level guard against zero-field `complete` (C2 defence-in-depth) |

---

## Task 1: Evaluator unit tests (pure function — no mocks needed)

**Files:**
- Create: `backend/tests/test_pipeline.py`

The evaluator is correct as-is. These tests establish a baseline for the pure logic and confirm `evaluate([])` intentionally returns `needs_review=False` (the fix for empty-from-failure lives in the pipeline, not the evaluator).

- [ ] **Step 1: Create the test file with evaluator unit tests**

Create `backend/tests/test_pipeline.py`:

```python
"""
Pipeline and extraction engine tests.

All Claude calls are mocked via `patch("app.services.extraction_engine.client")`.
_run_pipeline is called directly (not through the HTTP router) so we can
inspect DB state after each step without fighting background-task timing.
"""
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.models.document import Document
from app.models.document_extraction import DocumentExtraction
from app.models.document_schema import DocumentSchema
from app.models.user import User
from app.models.workspace import Workspace
from app.services.extraction_evaluator import EvaluationResult, evaluate


# ── Evaluator unit tests ─────────────────────────────────────────────────────

def test_evaluate_returns_no_review_when_all_confident():
    extractions = [
        {"field_name": "grantor_name", "confidence": 0.95},
        {"field_name": "sale_price", "confidence": 0.90},
    ]
    result = evaluate(extractions, threshold=0.75)
    assert isinstance(result, EvaluationResult)
    assert result.needs_review is False
    assert result.low_confidence_fields == []
    assert result.total_fields == 2


def test_evaluate_flags_fields_below_threshold():
    extractions = [
        {"field_name": "grantor_name", "confidence": 0.95},
        {"field_name": "sale_price", "confidence": 0.40},
        {"field_name": "parcel_id", "confidence": 0.30},
    ]
    result = evaluate(extractions, threshold=0.75)
    assert result.needs_review is True
    assert "sale_price" in result.low_confidence_fields
    assert "parcel_id" in result.low_confidence_fields
    assert "grantor_name" not in result.low_confidence_fields
    assert result.total_fields == 3


def test_evaluate_empty_input_is_not_needs_review():
    # evaluate() is pure — empty list = no low-confidence fields = no review.
    # The pipeline (not the evaluator) is responsible for detecting API failure.
    result = evaluate([], threshold=0.75)
    assert result.needs_review is False
    assert result.total_fields == 0
```

- [ ] **Step 2: Run the evaluator tests to confirm they pass**

```
docker-compose run --rm -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test backend pytest tests/test_pipeline.py -v -k "evaluate"
```

Expected: 3 PASSED

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_pipeline.py
git commit -m "test: add extraction evaluator unit tests (H4 baseline)"
```

---

## Task 2: Pipeline happy-path test (H4 baseline)

**Files:**
- Modify: `backend/tests/test_pipeline.py`

This test must pass with the **current** code. It is the safety net that confirms we haven't broken the happy path after each fix.

- [ ] **Step 1: Add shared fixtures and happy-path test**

Append to `backend/tests/test_pipeline.py`:

```python
# ── Shared fixtures ──────────────────────────────────────────────────────────

@pytest.fixture
def user(db):
    u = User(
        id=str(uuid.uuid4()),
        email=f"pipeline_{uuid.uuid4()}@test.com",
        full_name="Pipeline Tester",
        password_hash="x",
    )
    db.add(u)
    db.flush()
    return u


@pytest.fixture
def workspace(db, user):
    ws = Workspace(
        id=str(uuid.uuid4()),
        name="Pipeline Workspace",
        vertical="general",
        created_by=user.id,
    )
    db.add(ws)
    db.flush()
    return ws


@pytest.fixture
def deed_schema(db):
    schema = DocumentSchema(
        id=str(uuid.uuid4()),
        document_type="DEED",
        display_name="Deed",
        vertical="general",
        schema_fields=[
            {"name": "grantor_name", "type": "name", "description": "Name of grantor"},
            {"name": "sale_price", "type": "currency", "description": "Sale price in dollars"},
        ],
        extraction_prompt="Extract the following fields from this deed.",
        version=1,
        is_active=True,
        parse_strategy="claude",
        default_confidence_threshold=0.75,
    )
    db.add(schema)
    db.commit()
    return schema


@pytest.fixture
def pending_doc(db, workspace, user, tmp_path):
    file_path = tmp_path / "test.pdf"
    file_path.write_bytes(b"%PDF-1.4 Grantor: Jane Smith")
    doc = Document(
        id=str(uuid.uuid4()),
        workspace_id=workspace.id,
        filename="test.pdf",
        original_filename="test.pdf",
        file_path=str(file_path),
        file_type="pdf",
        sha256_hash="abc123",
        source_type="upload",
        uploaded_by=user.id,
        extraction_status="pending",
    )
    db.add(doc)
    db.commit()
    return doc


def _mock_claude_extraction(mock_client, extractions: list[dict]):
    """Configure mock_client to return a valid extraction response."""
    import json
    payload = json.dumps({"extractions": extractions})
    mock_client.messages.create.return_value = MagicMock(
        content=[MagicMock(text=payload)],
        usage=MagicMock(input_tokens=100, output_tokens=50),
    )


# ── Happy-path test ──────────────────────────────────────────────────────────

def test_pipeline_happy_path_marks_complete_with_extractions(
    db, workspace, user, deed_schema, pending_doc
):
    """End-to-end: mocked Claude returns real fields → doc is complete, rows saved."""
    from app.services.document_pipeline import _run_pipeline

    with patch("app.services.document_pipeline.detect_document_type", return_value="DEED"), \
         patch("app.services.document_pipeline.extract_text", return_value="Grantor: Jane Smith"), \
         patch("app.services.document_pipeline.generate_standardized_name", return_value="deed.pdf"), \
         patch("app.services.extraction_engine.client") as mock_client:

        _mock_claude_extraction(mock_client, [
            {"field_name": "grantor_name", "field_value": "Jane Smith", "field_type": "name", "confidence": 0.95},
            {"field_name": "sale_price", "field_value": "285000", "field_type": "currency", "confidence": 0.88},
        ])

        _run_pipeline(
            pending_doc.id, b"%PDF-1.4 content", "test.pdf",
            workspace.id, user.id, db,
        )

    db.refresh(pending_doc)
    assert pending_doc.extraction_status == "complete"

    rows = db.query(DocumentExtraction).filter(
        DocumentExtraction.document_id == pending_doc.id
    ).all()
    assert len(rows) == 2
    names = {r.field_name for r in rows}
    assert "grantor_name" in names
    assert "sale_price" in names
```

- [ ] **Step 2: Run the happy-path test to confirm it passes with current code**

```
docker-compose run --rm -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test backend pytest tests/test_pipeline.py::test_pipeline_happy_path_marks_complete_with_extractions -v
```

Expected: PASSED

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_pipeline.py
git commit -m "test: add pipeline happy-path test with mocked Claude (H4)"
```

---

## Task 3: C2 — Write the failing tests

**Files:**
- Modify: `backend/tests/test_pipeline.py`

These tests should FAIL with current code (doc ends up `complete` instead of `failed`).

- [ ] **Step 1: Add C2 failure tests**

Append to `backend/tests/test_pipeline.py`:

```python
# ── C2: false-complete on extraction failure ─────────────────────────────────

def test_pipeline_marks_failed_when_all_claude_batches_raise(
    db, workspace, user, deed_schema, pending_doc
):
    """C2: API outage → all batches fail → doc must be 'failed', not 'complete'."""
    from app.services.document_pipeline import _run_pipeline

    with patch("app.services.document_pipeline.detect_document_type", return_value="DEED"), \
         patch("app.services.document_pipeline.extract_text", return_value="some deed text"), \
         patch("app.services.document_pipeline.generate_standardized_name", return_value="deed.pdf"), \
         patch("app.services.extraction_engine.client") as mock_client:

        mock_client.messages.create.side_effect = Exception("Claude API is unavailable")

        _run_pipeline(
            pending_doc.id, b"%PDF-1.4 content", "test.pdf",
            workspace.id, user.id, db,
        )

    db.refresh(pending_doc)
    assert pending_doc.extraction_status == "failed", (
        f"Expected 'failed' but got '{pending_doc.extraction_status}' — "
        "C2 bug: API failure silently reports complete"
    )
    assert pending_doc.extraction_error is not None

    rows = db.query(DocumentExtraction).filter(
        DocumentExtraction.document_id == pending_doc.id
    ).all()
    assert len(rows) == 0, "No extraction rows should exist when API failed"


def test_pipeline_marks_complete_when_schema_has_no_fields(
    db, workspace, user, tmp_path
):
    """Edge case: zero-field claude schema → complete is correct (no batches run)."""
    from app.services.document_pipeline import _run_pipeline

    schema = DocumentSchema(
        id=str(uuid.uuid4()),
        document_type="ZERO-FIELD",
        display_name="Zero Field",
        vertical="general",
        schema_fields=[],
        version=1,
        is_active=True,
        parse_strategy="claude",
        default_confidence_threshold=0.75,
    )
    db.add(schema)
    file_path = tmp_path / "zf.pdf"
    file_path.write_bytes(b"%PDF-1.4 x")
    doc = Document(
        id=str(uuid.uuid4()),
        workspace_id=workspace.id,
        filename="zf.pdf",
        original_filename="zf.pdf",
        file_path=str(file_path),
        file_type="pdf",
        sha256_hash="zf123",
        source_type="upload",
        uploaded_by=user.id,
        extraction_status="pending",
    )
    db.add(doc)
    db.commit()

    with patch("app.services.document_pipeline.detect_document_type", return_value="ZERO-FIELD"), \
         patch("app.services.document_pipeline.extract_text", return_value="content"), \
         patch("app.services.document_pipeline.generate_standardized_name", return_value="zf.pdf"), \
         patch("app.services.extraction_engine.client"):  # no calls expected

        _run_pipeline(doc.id, b"%PDF-1.4 x", "zf.pdf", workspace.id, user.id, db)

    db.refresh(doc)
    assert doc.extraction_status == "complete"
```

- [ ] **Step 2: Run C2 tests to confirm the right one fails**

```
docker-compose run --rm -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test backend pytest tests/test_pipeline.py -v -k "claude_batches_raise or no_fields"
```

Expected:
- `test_pipeline_marks_failed_when_all_claude_batches_raise` → **FAILED** (currently marks `complete`)
- `test_pipeline_marks_complete_when_schema_has_no_fields` → **PASSED**

- [ ] **Step 3: Commit the failing test**

```bash
git add backend/tests/test_pipeline.py
git commit -m "test: add failing C2 test — API outage should mark failed not complete"
```

---

## Task 4: C2 — Fix extraction engine and evaluator

**Files:**
- Modify: `backend/app/services/extraction_engine.py`
- Modify: `backend/app/services/extraction_evaluator.py`
- Modify: `backend/app/services/document_pipeline.py`

- [ ] **Step 1: Add `ExtractionBatchError` and update `_extract_batch` in `extraction_engine.py`**

Add the exception class after the imports block (after `logger = logging.getLogger(__name__)`):

```python
class ExtractionBatchError(Exception):
    """Raised by _extract_batch when a Claude API call fails.
    Distinct from an empty result so callers can tell API failure from genuine
    zero-extraction (e.g., schema has no fields, or document has no matching data).
    """
```

In `_extract_batch`, replace the `except Exception as e:` block (lines 254–268) with:

```python
    except Exception as e:
        latency_ms = int((time.time() - start) * 1000)
        _log_claude_call(
            call_type=call_type,
            latency_ms=latency_ms,
            prompt_chars=len(prompt),
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
```

- [ ] **Step 2: Update `extract_fields` in `extraction_engine.py` to track batch failures**

Replace the `extract_fields` function body (everything after the docstring and the `if not fields: return []` check):

```python
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
    batches = [fields[i: i + BATCH_SIZE] for i in range(0, len(fields), BATCH_SIZE)]
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

    if batch_errors == len(batches):
        raise ExtractionBatchError(
            f"All {len(batches)} extraction batch(es) failed for schema "
            f"{schema.document_type} — Claude API may be unavailable"
        )

    if batch_errors > 0:
        logger.warning(
            f"Extraction partial: {batch_errors}/{len(batches)} batches failed, "
            f"{len(all_extractions)} fields extracted for schema {schema.document_type}"
        )

    logger.info(
        f"Extraction complete: {len(all_extractions)} fields from "
        f"{len(batches)} batch(es) for schema {schema.document_type}"
    )
    return all_extractions
```

- [ ] **Step 3: Update `extraction_evaluator.py` to import and handle `ExtractionBatchError`**

At the top of `extraction_evaluator.py`, update the import line:

```python
from app.services.extraction_engine import _extract_batch, save_extractions, ExtractionBatchError
```

In `run_retry`, wrap the `_extract_batch` call:

```python
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

- [ ] **Step 4: Add pipeline-level guard in `document_pipeline.py` (defence-in-depth)**

In `_run_pipeline`, after the `save_extractions(...)` call and before step 6b (evaluator), add:

```python
    # C2 guard: a claude schema with defined fields that yielded zero rows is a failure,
    # not a silent complete. (extract_fields raises if all batches failed; this catches
    # the rare case where batches succeed but Claude returns no extractions.)
    if (
        schema.parse_strategy == "claude"
        and schema.schema_fields
        and not raw_extractions
    ):
        _fail(doc, "Extraction returned zero fields — possible API outage or empty response", db)
        return
```

- [ ] **Step 5: Run C2 tests to confirm the failing test now passes**

```
docker-compose run --rm -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test backend pytest tests/test_pipeline.py -v -k "claude_batches_raise or no_fields"
```

Expected: both PASSED

- [ ] **Step 6: Run full test suite to verify nothing regressed**

```
docker-compose run --rm -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test backend pytest tests/ -v
```

Expected: all existing tests pass

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/extraction_engine.py \
        backend/app/services/extraction_evaluator.py \
        backend/app/services/document_pipeline.py
git commit -m "fix(C2): raise ExtractionBatchError on API failure instead of silent empty"
```

---

## Task 5: H5 — Write the failing text-truncation test

**Files:**
- Modify: `backend/tests/test_pipeline.py`

- [ ] **Step 1: Add H5 test**

Append to `backend/tests/test_pipeline.py`:

```python
# ── H5: 4000-char text cap ────────────────────────────────────────────────────

def test_extraction_sends_full_text_beyond_4000_chars(db, deed_schema):
    """H5: Claude must receive OCR text that extends past the old 4000-char cap."""
    from app.services.extraction_engine import extract_fields

    # Build text where a critical value appears at position 5000
    padding = "A" * 4500
    long_ocr = f"{padding} GRANTOR_EVIDENCE_AT_5000"
    assert len(long_ocr) > 4000

    captured_prompts = []

    def capture_call(**kwargs):
        msg = kwargs.get("messages", [{}])[0].get("content", "")
        captured_prompts.append(msg)
        return MagicMock(
            content=[MagicMock(text='{"extractions": []}')],
            usage=MagicMock(input_tokens=10, output_tokens=5),
        )

    with patch("app.services.extraction_engine.client") as mock_client:
        mock_client.messages.create.side_effect = capture_call
        extract_fields(long_ocr, deed_schema)

    assert captured_prompts, "Expected at least one Claude call"
    assert "GRANTOR_EVIDENCE_AT_5000" in captured_prompts[0], (
        "Text beyond 4000 chars was not sent to Claude — H5 truncation bug still present"
    )
```

- [ ] **Step 2: Run H5 test to confirm it fails**

```
docker-compose run --rm -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test backend pytest tests/test_pipeline.py::test_extraction_sends_full_text_beyond_4000_chars -v
```

Expected: FAILED — `GRANTOR_EVIDENCE_AT_5000` not in captured prompt

- [ ] **Step 3: Commit the failing test**

```bash
git add backend/tests/test_pipeline.py
git commit -m "test: add failing H5 test — text beyond 4000 chars must reach Claude"
```

---

## Task 6: H5 — Fix the text cap in `extraction_engine.py`

**Files:**
- Modify: `backend/app/services/extraction_engine.py`

- [ ] **Step 1: Add `TEXT_LIMIT` constant and update `_extract_batch`**

After the `BATCH_SIZE = 40` constant, add:

```python
# Maximum OCR text characters sent per extraction batch.
# 200_000 chars ≈ 50k tokens — well within Claude Sonnet 4.6's context window.
# The old 4000-char cap silently dropped evidence from multi-page documents.
TEXT_LIMIT = 200_000
```

In `_extract_batch`, find the prompt template that contains `{ocr_text[:4000]}` and replace it. The full prompt block should now read:

```python
    if len(ocr_text) > TEXT_LIMIT:
        logger.warning(
            f"OCR text ({len(ocr_text)} chars) exceeds TEXT_LIMIT ({TEXT_LIMIT}); "
            "truncating for extraction"
        )

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
{ocr_text[:TEXT_LIMIT]}"""
```

- [ ] **Step 2: Run H5 test to confirm it passes**

```
docker-compose run --rm -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test backend pytest tests/test_pipeline.py::test_extraction_sends_full_text_beyond_4000_chars -v
```

Expected: PASSED

- [ ] **Step 3: Run full test suite**

```
docker-compose run --rm -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test backend pytest tests/ -v
```

Expected: all pass

- [ ] **Step 4: Commit**

```bash
git add backend/app/services/extraction_engine.py
git commit -m "fix(H5): raise text cap from 4000 to 200_000 chars so full document reaches Claude"
```

---

## Task 7: L3 — Write the failing file-cleanup test

**Files:**
- Modify: `backend/tests/test_pipeline.py`

- [ ] **Step 1: Add L3 test**

Append to `backend/tests/test_pipeline.py`:

```python
# ── L3: orphaned file cleanup ─────────────────────────────────────────────────

def test_pipeline_deletes_file_on_ocr_failure(db, workspace, user, deed_schema, tmp_path):
    """L3: a file written to disk before OCR must be deleted when the pipeline fails."""
    from app.services.document_pipeline import _run_pipeline

    file_path = tmp_path / "orphan.pdf"
    file_path.write_bytes(b"%PDF-1.4 x")
    doc = Document(
        id=str(uuid.uuid4()),
        workspace_id=workspace.id,
        filename="orphan.pdf",
        original_filename="orphan.pdf",
        file_path=str(file_path),
        file_type="pdf",
        sha256_hash="orph123",
        source_type="upload",
        uploaded_by=user.id,
        extraction_status="pending",
    )
    db.add(doc)
    db.commit()

    assert file_path.exists(), "File must exist before pipeline runs"

    with patch("app.services.document_pipeline.extract_text", side_effect=Exception("OCR failed")):
        _run_pipeline(doc.id, b"%PDF-1.4 x", "orphan.pdf", workspace.id, user.id, db)

    db.refresh(doc)
    assert doc.extraction_status == "failed"
    assert not file_path.exists(), (
        "L3: orphaned file still on disk after pipeline failure"
    )


def test_pipeline_preserves_file_on_success(db, workspace, user, deed_schema, pending_doc):
    """Sanity: successful pipeline must NOT delete the stored file."""
    from app.services.document_pipeline import _run_pipeline

    file_path = Path(pending_doc.file_path)
    assert file_path.exists()

    with patch("app.services.document_pipeline.detect_document_type", return_value="DEED"), \
         patch("app.services.document_pipeline.extract_text", return_value="deed content"), \
         patch("app.services.document_pipeline.generate_standardized_name", return_value="deed.pdf"), \
         patch("app.services.extraction_engine.client") as mock_client:

        _mock_claude_extraction(mock_client, [
            {"field_name": "grantor_name", "field_value": "Jane Smith", "field_type": "name", "confidence": 0.95},
        ])

        _run_pipeline(pending_doc.id, b"%PDF-1.4 x", "test.pdf", workspace.id, user.id, db)

    db.refresh(pending_doc)
    assert pending_doc.extraction_status == "complete"
    assert file_path.exists(), "Successful pipeline must not delete the stored file"
```

- [ ] **Step 2: Run L3 tests to confirm the cleanup test fails**

```
docker-compose run --rm -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test backend pytest tests/test_pipeline.py -v -k "file"
```

Expected:
- `test_pipeline_deletes_file_on_ocr_failure` → **FAILED** (file not deleted)
- `test_pipeline_preserves_file_on_success` → **PASSED**

- [ ] **Step 3: Commit the failing test**

```bash
git add backend/tests/test_pipeline.py
git commit -m "test: add failing L3 test — file should be deleted on pipeline failure"
```

---

## Task 8: L3 — Fix `_fail` to clean up the stored file

**Files:**
- Modify: `backend/app/services/document_pipeline.py`

- [ ] **Step 1: Update `_fail` to delete the stored file**

At the top of `document_pipeline.py`, confirm `from pathlib import Path` is already imported (it is, at line 22).

Replace the `_fail` function:

```python
def _fail(doc: Document, error: str, db: Session) -> None:
    """Mark a document as failed and clean up its stored file (L3)."""
    doc.extraction_status = "failed"
    doc.extraction_error = error[:500]
    db.commit()
    logger.error(f"Pipeline failed for doc {doc.id}: {error}")

    if doc.file_path:
        try:
            Path(doc.file_path).unlink(missing_ok=True)
        except Exception as e:
            logger.warning(f"File cleanup failed for doc {doc.id}: {e}")

    try:
        audit.log(
            db,
            action="upload_failed",
            user_id=doc.uploaded_by,
            workspace_id=doc.workspace_id,
            entity_type="document",
            entity_id=doc.id,
            after_state={"error": error[:500], "status": "failed"},
        )
    except Exception as e:
        logger.warning(f"Audit log failed for _fail on doc {doc.id}: {e}")
```

- [ ] **Step 2: Run L3 tests to confirm both pass**

```
docker-compose run --rm -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test backend pytest tests/test_pipeline.py -v -k "file"
```

Expected: both PASSED

- [ ] **Step 3: Run full test suite**

```
docker-compose run --rm -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test backend pytest tests/ -v
```

Expected: all pass

- [ ] **Step 4: Commit**

```bash
git add backend/app/services/document_pipeline.py
git commit -m "fix(L3): delete stored file in _fail so no orphans on pipeline failure"
```

---

## Task 9: Run full suite + mark audit findings resolved

- [ ] **Step 1: Run the complete test suite one final time**

```
docker-compose run --rm -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test backend pytest tests/ -v
```

Expected: all pass, with `test_pipeline.py` contributing 10+ new passing tests

- [ ] **Step 2: Update the audit doc**

In `docs/code-audit-2026-05-29.md`, update the remediation phase table:

```markdown
| 3 | H4 → C2, H5, L3 | Extraction pipeline correctness | ✅ Done — merged YYYY-MM-DD |
```

And in the "Suggested fix order" section, mark C2, H4, H5, L3 as done.

- [ ] **Step 3: Open the PR**

```bash
git push origin feat/phase3-extraction-pipeline-correctness
```

Then open a PR against `main`. Use `/verity-prism-pr-description` to generate the PR body.

---

## Self-Review Checklist

**Spec coverage:**
- H4 (no pipeline tests) → Tasks 1, 2, 3, 5, 7 — all covered with TDD cycle
- C2 (false-complete on empty extraction) → Task 3 (failing test), Task 4 (fix)
- H5 (4000-char cap) → Task 5 (failing test), Task 6 (fix)
- L3 (orphaned file) → Task 7 (failing test), Task 8 (fix)
- Zero-field schema edge case → Task 3 (verified stays `complete`)
- File preserved on success → Task 7 (sanity test)

**Placeholder scan:** No TBDs. Every step shows the complete code change.

**Type consistency:**
- `ExtractionBatchError` defined in Task 4 Step 1, imported in evaluator Step 3
- `_mock_claude_extraction` helper defined in Task 2, reused in Task 7
- `TEXT_LIMIT` defined in Task 6 Step 1, used in same step
- `pending_doc` fixture defined in Task 2, reused across Tasks 4 and 7
