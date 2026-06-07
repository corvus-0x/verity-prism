# Phase 2F Plan 1 — Commercial Readiness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Cut per-document extraction cost (prompt caching + Haiku routing) and add the usage-metering query that Phase 4A billing builds on.

**Architecture:** Three independent backend changes. (1) Restructure the extraction prompt so the static schema field-description block is a cacheable content block. (2) Route field extraction to Haiku, keep chat + type detection on Sonnet, via constants. (3) Add a read-only query over `claude_call_logs` that sums tokens and counts documents per workspace per billing period.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.0, Anthropic SDK, pytest. Tests run in Docker against `catalyst_test`.

**Spec:** `docs/superpowers/specs/2026-05-31-phase2f-connectors-design.md` (Part A)

**Reference — running a single test (from CLAUDE.md):**
```bash
docker-compose run --rm -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test backend pytest tests/test_metering.py -v
```

---

## File Structure

- `backend/app/services/claude_client.py` — **modify.** Add `EXTRACTION_MODEL` and `CHAT_MODEL` constants. Single source of truth for model selection.
- `backend/app/services/extraction_engine.py` — **modify.** `_extract_batch`: split prompt into cacheable + dynamic content blocks (A1); default field extraction to `EXTRACTION_MODEL` (A2). Keep type detection on Sonnet.
- `backend/app/services/ai_engine.py` — **modify.** Use `CHAT_MODEL` (A2).
- `backend/app/services/metering.py` — **create.** `get_workspace_usage()` (A3).
- `backend/tests/test_metering.py` — **create.** Metering query tests.
- `backend/tests/test_extraction_caching.py` — **create.** Caching block + model-routing assertions.

---

## Task 1: Model routing constants

**Files:**
- Modify: `backend/app/services/claude_client.py`
- Test: `backend/tests/test_claude_client.py` (exists — add one test)

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_claude_client.py`:

```python
def test_model_constants_are_distinct():
    from app.services import claude_client

    # Extraction uses the cheaper model; chat uses the stronger one.
    assert claude_client.EXTRACTION_MODEL == "claude-haiku-4-5-20251001"
    assert claude_client.CHAT_MODEL == "claude-sonnet-4-6"
    assert claude_client.EXTRACTION_MODEL != claude_client.CHAT_MODEL
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
docker-compose run --rm -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test backend pytest tests/test_claude_client.py::test_model_constants_are_distinct -v
```
Expected: FAIL — `AttributeError: module 'app.services.claude_client' has no attribute 'EXTRACTION_MODEL'`

- [ ] **Step 3: Add the constants**

In `backend/app/services/claude_client.py`, after the imports / near the top of the module, add:

```python
# Model routing by task (Phase 2F A2).
# Field extraction on clean, structured documents does not need Sonnet —
# Haiku is ~4x cheaper and adequate. Chat reasons across many documents and
# stays on Sonnet. Type detection of ambiguous documents also stays on Sonnet
# (set in extraction_engine.detect_document_type, not here).
EXTRACTION_MODEL = "claude-haiku-4-5-20251001"
CHAT_MODEL = "claude-sonnet-4-6"
```

- [ ] **Step 4: Run test to verify it passes**

Run:
```bash
docker-compose run --rm -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test backend pytest tests/test_claude_client.py::test_model_constants_are_distinct -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/claude_client.py backend/tests/test_claude_client.py
git commit -m "feat: add EXTRACTION_MODEL/CHAT_MODEL routing constants

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 2: Route field extraction to Haiku

**Files:**
- Modify: `backend/app/services/extraction_engine.py`
- Test: `backend/tests/test_extraction_caching.py` (create)

**Reality check (verified against source):** `_extract_batch` does NOT take a `model` param — line 242 hardcodes `model="claude-sonnet-4-6"`. There is no `MODEL` module constant. The signature is `_extract_batch(ocr_text, fields_batch, schema, document_id=None, workspace_id=None, call_type=..., attempt=...)`. `detect_document_type` makes its OWN Claude call at line ~145 (also hardcoded `claude-sonnet-4-6`), separate from `_extract_batch` — so it stays on Sonnet automatically as long as we only change line 242.

The change: replace the hardcoded `"claude-sonnet-4-6"` inside `_extract_batch`'s `messages.create` with `EXTRACTION_MODEL`. Leave the type-detection call (line ~145) on its hardcoded Sonnet string.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_extraction_caching.py`:

```python
from unittest.mock import MagicMock, patch

from app.models.document_schema import DocumentSchema
from app.services import extraction_engine
from app.services.claude_client import EXTRACTION_MODEL


def _mock_response():
    """Minimal Anthropic-style response with usage + JSON text block.
    _extract_batch parses json.loads(strip_json_fences(content[0].text)).get('extractions', []).
    """
    resp = MagicMock()
    block = MagicMock()
    block.text = '{"extractions": []}'
    resp.content = [block]
    resp.usage = MagicMock(
        input_tokens=10, output_tokens=5,
        cache_creation_input_tokens=0, cache_read_input_tokens=0,
    )
    return resp


def _schema():
    s = DocumentSchema(document_type="TEST", schema_fields=[
        {"name": "ein", "type": "string", "description": "EIN number"}
    ])
    s.id = "schema-1"
    return s


def test_extract_batch_uses_extraction_model():
    mock_client = MagicMock()
    mock_client.messages.create.return_value = _mock_response()

    with patch("app.services.claude_client.get_client", return_value=mock_client):
        extraction_engine._extract_batch(
            "some document text",
            [{"name": "ein", "type": "string", "description": "EIN number"}],
            _schema(),
            document_id=None, workspace_id=None,
            call_type="extraction_batch", attempt=1,
        )

    _, kwargs = mock_client.messages.create.call_args
    assert kwargs["model"] == EXTRACTION_MODEL
```

> Verify the exact positional order of `_extract_batch` against the source before running —
> the first two args are `ocr_text` then `fields_batch`. Match the keyword names
> (`call_type`, `attempt`) to the real signature.

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
docker-compose run --rm -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test backend pytest tests/test_extraction_caching.py::test_extract_batch_uses_extraction_model -v
```
Expected: FAIL — model is the hardcoded `claude-sonnet-4-6`, not Haiku.

- [ ] **Step 3: Route field extraction to EXTRACTION_MODEL**

In `backend/app/services/extraction_engine.py`:

1. Extend the existing import (line 16 is `from app.services import claude_client`). Add:

```python
from app.services.claude_client import EXTRACTION_MODEL
```

2. At the `_extract_batch` `messages.create` call (line ~242), change:

```python
        response = claude_client.get_client().messages.create(
            model=EXTRACTION_MODEL,   # was "claude-sonnet-4-6"
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
```

3. **Do NOT touch** the `detect_document_type` Claude call (line ~145, `model="claude-sonnet-4-6"`) — type detection stays on Sonnet.

- [ ] **Step 4: Run test to verify it passes**

Run:
```bash
docker-compose run --rm -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test backend pytest tests/test_extraction_caching.py -v
```
Expected: PASS

- [ ] **Step 5: Run the full extraction-related suite to confirm no regression**

Run:
```bash
docker-compose run --rm -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test backend pytest tests/test_extractions.py tests/test_pipeline.py -v
```
Expected: PASS (all existing extraction/pipeline tests still green)

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/extraction_engine.py backend/tests/test_extraction_caching.py
git commit -m "feat: route field extraction to Haiku, keep type detection on Sonnet

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 3: Route AI chat to CHAT_MODEL

**Files:**
- Modify: `backend/app/services/ai_engine.py`
- Test: `backend/tests/test_ai.py` (exists — add one test)

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_ai.py`:

```python
def test_chat_uses_chat_model(client, auth_headers):
    """ai_engine.chat must call Claude with CHAT_MODEL (Sonnet)."""
    from unittest.mock import MagicMock, patch
    from app.services.claude_client import CHAT_MODEL

    mock_client = MagicMock()
    resp = MagicMock()
    text_block = MagicMock()
    text_block.type = "text"
    text_block.text = "answer"
    resp.content = [text_block]
    resp.stop_reason = "end_turn"
    resp.usage = MagicMock(input_tokens=1, output_tokens=1)
    mock_client.messages.create.return_value = resp

    with patch("app.services.claude_client.get_client", return_value=mock_client):
        from app.services import ai_engine
        ai_engine.chat(workspace_id="ws-1", user_message="hi", db=MagicMock())

    _, kwargs = mock_client.messages.create.call_args
    assert kwargs["model"] == CHAT_MODEL
```

> Note: adjust `ai_engine.chat(...)` argument names to match the real signature if different. The assertion that matters is `kwargs["model"] == CHAT_MODEL`.

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
docker-compose run --rm -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test backend pytest tests/test_ai.py::test_chat_uses_chat_model -v
```
Expected: FAIL — model arg is the hardcoded string, not `CHAT_MODEL` (test imports the constant; if `ai_engine` already uses the same literal the test still passes — in that case skip to Step 4 after switching to the constant for single-source-of-truth).

- [ ] **Step 3: Use the constant in ai_engine**

In `backend/app/services/ai_engine.py`:

1. Add to imports:

```python
from app.services.claude_client import CHAT_MODEL
```

2. Replace the hardcoded model string in the `messages.create(...)` call(s) with `model=CHAT_MODEL`. There may be two calls — the main tool-use loop and `_synthesis_pass`. Update both.

- [ ] **Step 4: Run test to verify it passes**

Run:
```bash
docker-compose run --rm -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test backend pytest tests/test_ai.py -v
```
Expected: PASS (all ai tests green)

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/ai_engine.py backend/tests/test_ai.py
git commit -m "feat: ai_engine uses CHAT_MODEL constant

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 4: Prompt caching on the schema field-description block

**Files:**
- Modify: `backend/app/services/extraction_engine.py`
- Test: `backend/tests/test_extraction_caching.py` (add tests)

**Reality check (verified against source):** `_extract_batch` builds one f-string `prompt`
(field instructions + `f"Document text:\n{ocr_text[:TEXT_LIMIT]}"` at the end, lines ~210–233)
and sends `messages=[{"role": "user", "content": prompt}]`. To cache the static part, split
that f-string at the `Document text:` boundary into two content blocks: the static
instruction block (with field definitions) carries `cache_control`, the per-document text is
a separate uncached block AFTER it.

> **Why order matters:** Anthropic caches the prefix up to and including the block marked
> with `cache_control`. The static (identical-across-documents) block must come FIRST; the
> per-document text must come AFTER so it is never part of the cached prefix.

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_extraction_caching.py` (reuses `_mock_response` and `_schema` from the model-routing test above):

```python
def test_extract_batch_marks_static_block_as_cacheable():
    mock_client = MagicMock()
    mock_client.messages.create.return_value = _mock_response()

    with patch("app.services.claude_client.get_client", return_value=mock_client):
        extraction_engine._extract_batch(
            "document body text here",
            [{"name": "ein", "type": "string", "description": "EIN number"}],
            _schema(),
            document_id=None, workspace_id=None,
            call_type="extraction_batch", attempt=1,
        )

    _, kwargs = mock_client.messages.create.call_args
    content = kwargs["messages"][0]["content"]

    assert isinstance(content, list)  # blocks, not a bare string

    cached = [b for b in content if b.get("cache_control")]
    assert len(cached) == 1
    assert cached[0]["cache_control"] == {"type": "ephemeral"}

    # Static block holds the field instructions; document text is a later, uncached block.
    cached_index = content.index(cached[0])
    doc_block = next(b for b in content if "document body text here" in b.get("text", ""))
    assert content.index(doc_block) > cached_index
    assert "cache_control" not in doc_block
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
docker-compose run --rm -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test backend pytest tests/test_extraction_caching.py::test_extract_batch_marks_static_block_as_cacheable -v
```
Expected: FAIL — `content` is currently a string, so `isinstance(content, list)` fails.

- [ ] **Step 3: Split the prompt into cached + dynamic blocks**

In `_extract_batch`, the prompt is currently built as one f-string ending in
`f"\n\nDocument text:\n{ocr_text[:TEXT_LIMIT]}"`. Split it: build the static portion
(everything BEFORE `Document text:`) as `static_prompt`, keep the document text separate,
and replace the `messages.create` content with a two-block list:

```python
    # static_prompt = the existing prompt text WITHOUT the trailing
    # "Document text:\n{ocr_text...}" section (field instructions + JSON shape).
    static_block = {
        "type": "text",
        "text": static_prompt,
        "cache_control": {"type": "ephemeral"},
    }
    document_block = {
        "type": "text",
        "text": f"Document text:\n{ocr_text[:TEXT_LIMIT]}",
    }

    response = claude_client.get_client().messages.create(
        model=EXTRACTION_MODEL,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": [static_block, document_block]}],
    )
```

Keep the existing response parsing (`strip_json_fences`, `.get("extractions", [])`, the
field/value normalisation loop) and the `_log_claude_call` calls exactly as they are — only
the request construction changes. Note `prompt_chars=len(prompt)` in `_log_claude_call` now
needs a defined length; pass `prompt_chars=len(static_prompt) + len(ocr_text[:TEXT_LIMIT])`.

- [ ] **Step 4: Run test to verify it passes**

Run:
```bash
docker-compose run --rm -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test backend pytest tests/test_extraction_caching.py -v
```
Expected: PASS

- [ ] **Step 5: Log cache token counts to claude_call_logs**

The response `usage` now includes `cache_creation_input_tokens` and `cache_read_input_tokens`. If the call-logging path (`log_claude_call` / `claude_call_logger`) records `input_tokens`/`output_tokens`, extend it to also capture these two when present. Add a test:

```python
def test_extract_batch_logging_tolerates_cache_usage_fields():
    """Cache usage fields present on usage object don't break logging."""
    mock_client = MagicMock()
    resp = _mock_response()
    resp.usage.cache_creation_input_tokens = 120
    resp.usage.cache_read_input_tokens = 0
    mock_client.messages.create.return_value = resp

    with patch("app.services.claude_client.get_client", return_value=mock_client):
        result = extraction_engine._extract_batch(
            schema_fields=[{"name": "ein", "type": "string", "description": "EIN"}],
            ocr_text="text",
            attempt=1,
            call_type="extraction_batch",
            document_id=None,
            workspace_id=None,
            schema_id=None,
        )
    assert result == []
```

> If `claude_call_logs` has no columns for cache tokens, do NOT add a migration in this plan — logging the two new fields is optional polish. The test above only asserts that their presence doesn't crash the existing path. Capturing them in the table is a follow-on once the dashboard consumes them.

- [ ] **Step 6: Run test to verify it passes**

Run:
```bash
docker-compose run --rm -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test backend pytest tests/test_extraction_caching.py -v
```
Expected: PASS

- [ ] **Step 7: Run the full pipeline suite (regression)**

Run:
```bash
docker-compose run --rm -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test backend pytest tests/test_pipeline.py tests/test_extractions.py -v
```
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add backend/app/services/extraction_engine.py backend/tests/test_extraction_caching.py
git commit -m "feat: cache schema field descriptions in extraction prompt

Static field-description block marked ephemeral; per-document text moved to a
separate uncached block after it. 60-90% input-token reduction on extraction.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 5: Usage metering query

**Files:**
- Create: `backend/app/services/metering.py`
- Test: `backend/tests/test_metering.py`

Read-only aggregation over `claude_call_logs`. No new table, no endpoint. The deliverable
is the query + tests; Phase 4A builds enforcement and UI on top.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_metering.py`:

```python
from datetime import UTC, datetime, timedelta

from app.models.claude_call_log import ClaudeCallLog
from app.services.metering import get_workspace_usage


def _log(db, workspace_id, input_tokens, output_tokens, when, document_id="doc-1"):
    row = ClaudeCallLog(
        call_type="extraction_batch",
        workspace_id=workspace_id,
        document_id=document_id,
        model="claude-haiku-4-5-20251001",
        attempt=1,
        latency_ms=100,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        success=True,
    )
    # called_at is the timestamp column on claude_call_logs
    row.called_at = when
    db.add(row)
    db.commit()
    return row


def test_usage_sums_tokens_within_period(db_session):
    ws = "ws-meter-1"
    period_start = datetime(2026, 5, 1, tzinfo=UTC)
    inside = datetime(2026, 5, 15, tzinfo=UTC)
    before = datetime(2026, 4, 20, tzinfo=UTC)

    _log(db_session, ws, 100, 50, inside, document_id="doc-a")
    _log(db_session, ws, 200, 80, inside, document_id="doc-b")
    _log(db_session, ws, 999, 999, before, document_id="doc-old")  # excluded

    usage = get_workspace_usage(ws, period_start, db_session)

    assert usage["input_tokens"] == 300
    assert usage["output_tokens"] == 130
    assert usage["total_tokens"] == 430
    assert usage["documents_processed"] == 2  # distinct document_ids inside period
    assert usage["period_start"] == period_start


def test_usage_empty_for_workspace_with_no_calls(db_session):
    usage = get_workspace_usage("ws-none", datetime(2026, 5, 1, tzinfo=UTC), db_session)
    assert usage["input_tokens"] == 0
    assert usage["output_tokens"] == 0
    assert usage["total_tokens"] == 0
    assert usage["documents_processed"] == 0
```

> `db_session` is the test DB session fixture from `conftest.py`. If the fixture has a
> different name (e.g. `db`), use that. Check `backend/tests/conftest.py` for the exact name.

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
docker-compose run --rm -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test backend pytest tests/test_metering.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.metering'`

- [ ] **Step 3: Implement the metering query**

Create `backend/app/services/metering.py`:

```python
from datetime import datetime

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.claude_call_log import ClaudeCallLog


def get_workspace_usage(
    workspace_id: str, billing_period_start: datetime, db: Session
) -> dict:
    """Sum tokens and count documents processed for a workspace since a period start.

    Reads claude_call_logs only — no new table. Data layer for Phase 4A tier
    enforcement; this function answers "how much has this workspace used this period."
    documents_processed counts distinct document_ids with at least one logged call.
    """
    rows = db.query(ClaudeCallLog).filter(
        ClaudeCallLog.workspace_id == workspace_id,
        ClaudeCallLog.called_at >= billing_period_start,
    )

    input_tokens = 0
    output_tokens = 0
    document_ids = set()
    for row in rows:
        input_tokens += row.input_tokens or 0
        output_tokens += row.output_tokens or 0
        if row.document_id is not None:
            document_ids.add(row.document_id)

    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
        "documents_processed": len(document_ids),
        "period_start": billing_period_start,
    }
```

> The loop is intentional over a `func.sum` aggregate: it computes token sums AND the
> distinct-document count in one pass, and stays readable. Volumes per workspace per
> period are small (hundreds–thousands of rows). If profiling later shows this is hot,
> swap to two aggregate queries (`func.sum`, `func.count(distinct(...))`).

- [ ] **Step 4: Run test to verify it passes**

Run:
```bash
docker-compose run --rm -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test backend pytest tests/test_metering.py -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/metering.py backend/tests/test_metering.py
git commit -m "feat: workspace usage metering query over claude_call_logs

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 6: Full suite + branch wrap

- [ ] **Step 1: Run the entire backend suite**

Run:
```bash
docker-compose run --rm -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test backend pytest tests/ -v
```
Expected: All green. Baseline before this plan was 123 backend tests; this plan adds the metering + caching tests.

- [ ] **Step 2: Update build inventory**

In `docs/build-inventory.md`, add a service entry for `metering.py` (Engine, "workspace usage query over claude_call_logs — Phase 4A billing data layer") and note in the extraction_engine entry that field extraction runs on Haiku with cached field descriptions, type detection stays on Sonnet. Add a row to the Update Log with today's date.

- [ ] **Step 3: Commit**

```bash
git add docs/build-inventory.md
git commit -m "docs: build inventory — metering, model routing, prompt caching

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Self-Review Notes

- **Spec coverage:** A1 caching (Task 4), A2 model routing (Tasks 1–3), A3 metering (Task 5). All of Part A covered.
- **Type consistency:** `EXTRACTION_MODEL` / `CHAT_MODEL` defined once in `claude_client.py` (Task 1), consumed in Tasks 2–3. `get_workspace_usage` return keys defined in Task 5 test match the implementation.
- **Known adjustment points (flagged inline, not placeholders):** the `ai_engine.chat` signature (Task 3) and the conftest session-fixture name (Task 5) must be matched to the real code — both call-outs tell the engineer exactly what to check.
- **Out of scope (correctly deferred):** persisting cache-token columns in `claude_call_logs` — only matters once the observability dashboard reads them; Task 4 Step 5 ensures their presence doesn't break logging without adding a migration.
