# Brief Observability & Citation Resolution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the brief backend (Plan 3): make synthesis observable (logged to `claude_call_logs` + metering) and its citations traceable (resolve an `extraction_id` to its source document/field/value/region), and surface dropped-citation counts.

**Architecture:** Three additive workstreams on the merged synthesis layer — (1) a citation-resolve endpoint pair on the briefs router that resolves `document_extractions` ids (workspace-scoped) to their source detail incl. the `evidence` region JSON; (2) `_synthesize` writes a `call_type="brief_synthesis"` row to `claude_call_logs` (metering picks it up automatically); (3) `_validate_and_annotate` counts dropped (unfalsifiable) claims, surfaced in the `brief_generated` audit entry. No schema changes.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy, PostgreSQL, Anthropic Claude (`CHAT_MODEL`), pytest, docker-compose.

**Spec:** `docs/superpowers/specs/2026-06-15-brief-observability-citation-resolution-design.md`.

**Conventions:**
- Run tests in Docker: `docker-compose run --rm -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test backend pytest <path> -v`. Container `verity-prism-db-1` must be up; don't stop/recreate containers.
- Mock Claude by patching `app.services.claude_client.get_client`.
- ruff is not in the Docker image — run it from the host (`ruff check ...` or `/c/Users/tjcol/AppData/Local/Programs/Python/Python314/Scripts/ruff.exe check ...`).
- Don't stage `backend/notebooks/`.

**Reused (verified on `main`):**
- `synthesis_service.py`: `_validate_and_annotate(brief, evidence)`, `_synthesize(evidence, saliences)`, `synthesize_brief(workspace_id, db)`, `store_brief`. `time`, `logging`, `CHAT_MODEL`, `claude_client` already imported.
- `_log_claude_call` pattern (`extraction_engine.py:43`): opens its own `SessionLocal`, swallows all exceptions, writes a `ClaudeCallLog`.
- `ClaudeCallLog` columns: `call_type, document_id, workspace_id, schema_id, model, attempt, success, latency_ms, input_tokens, output_tokens, prompt_chars (NOT NULL), response_chars, error_message, called_at`.
- `metering.get_workspace_usage` sums `input_tokens`/`output_tokens` from `claude_call_logs` by workspace — **new `brief_synthesis` rows are included automatically; no metering change**. (It counts distinct `document_id` for `documents_processed`; brief rows have no `document_id`, so doc counts are unaffected — correct.)
- Briefs router (`routers/briefs.py`): `prefix="/workspaces/{workspace_id}"`, `get_workspace_or_404` gate, `audit.log(action="brief_generated", after_state={...})`.
- `DocumentExtraction` columns incl. `evidence` (JSONB region capture). `Document.is_deleted`, `Document.detected_doc_type`, `Document.filename`.

---

## File Structure

| File | Change |
|------|--------|
| `backend/app/services/synthesis_service.py` | `_validate_and_annotate` returns `claims_dropped`; add `_log_synthesis_call`; `_synthesize` times + logs + takes `workspace_id`; `synthesize_brief` threads it |
| `backend/app/routers/briefs.py` | add `claims_dropped` to audit; add `GET`/`POST` citation-resolve endpoints |
| `backend/tests/test_synthesis_service.py` | update one exact-equality test; add dropped-count + logging tests |
| `backend/tests/test_briefs_api.py` | add resolve-endpoint + audit-dropped tests |

No migration (no schema change).

---

## Task 1: Dropped-citation count

**Files:**
- Modify: `backend/app/services/synthesis_service.py` (`_validate_and_annotate`)
- Modify: `backend/app/routers/briefs.py` (audit payload)
- Test: `backend/tests/test_synthesis_service.py`

- [ ] **Step 1: Update the now-stale test + add the dropped-count test**

In `backend/tests/test_synthesis_service.py`, find `test_validate_handles_missing_keys_gracefully` and change its assertion to include the new key:

```python
def test_validate_handles_missing_keys_gracefully():
    out = _validate_and_annotate({}, [])
    assert out == {"summary": "", "claims": [], "claims_dropped": 0}
```

Then add this new test next to it:

```python
def test_validate_counts_dropped_claims():
    evidence = [_ev("e1")]
    raw = {
        "summary": "s",
        "claims": [
            {"text": "valid", "sources": ["e1"], "signal_type": "general"},
            {"text": "fabricated", "sources": ["ghost"], "signal_type": "general"},
            {"text": "uncited", "sources": [], "signal_type": "general"},
        ],
    }
    out = _validate_and_annotate(raw, evidence)
    assert [c["text"] for c in out["claims"]] == ["valid"]
    assert out["claims_dropped"] == 2
```

(The `_ev` helper already exists at the top of this test file.)

- [ ] **Step 2: Run to verify the new test fails (and the updated one)**

Run: `docker-compose run --rm -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test backend pytest tests/test_synthesis_service.py::test_validate_counts_dropped_claims tests/test_synthesis_service.py::test_validate_handles_missing_keys_gracefully -v`
Expected: both FAIL — `claims_dropped` not in the returned dict yet.

- [ ] **Step 3: Implement the count in `_validate_and_annotate`**

Replace the `_validate_and_annotate` body in `backend/app/services/synthesis_service.py` with:

```python
def _validate_and_annotate(brief: dict, evidence: list[Evidence]) -> dict:
    """Drop claims that cite no valid evidence id, strip unknown ids from the
    rest, annotate each surviving claim with grounding_confidence = the minimum
    confidence of its cited rows, and report how many claims were dropped (an
    invalid-citation / hallucination signal).
    """
    by_id = {e.id: e for e in evidence}
    claims = []
    dropped = 0
    for claim in brief.get("claims", []) or []:
        sources = [s for s in (claim.get("sources") or []) if s in by_id]
        if not sources:
            dropped += 1  # unfalsifiable — a claim with no real citation is dropped
            continue
        claim["sources"] = sources
        claim["grounding_confidence"] = round(min(by_id[s].confidence for s in sources), 4)
        claims.append(claim)
    if dropped:
        logger.warning("Brief synthesis dropped %d claim(s) with invalid citations", dropped)
    return {
        "summary": brief.get("summary", "") or "",
        "claims": claims,
        "claims_dropped": dropped,
    }
```

(`synthesize_brief` does `brief.update(meta)` where `meta` has no `claims_dropped`, so the count survives; `store_brief` only reads `summary`/`claims`/`model`/`latency_ms`/`input_tokens`/`output_tokens`, so the extra key is ignored.)

- [ ] **Step 4: Surface the count in the audit entry (router)**

In `backend/app/routers/briefs.py`, in `generate_brief`, change the `after_state` dict:

```python
    audit.log(
        db,
        action="brief_generated",
        user_id=user.id,
        workspace_id=workspace_id,
        entity_type="brief",
        entity_id=row.id,
        after_state={
            "version": row.version,
            "claim_count": len(row.claims),
            "claims_dropped": brief.get("claims_dropped", 0),
        },
    )
```

- [ ] **Step 5: Add an API test asserting the audit captures the dropped count**

Append to `backend/tests/test_briefs_api.py` (the `_fake_response`, `_seed`, `_user_id` helpers already exist there):

```python
from app.models.audit import AuditLog


@patch("app.services.claude_client.get_client")
def test_generate_brief_audits_dropped_claims(mock_client, client, auth_headers, db):
    mock_client.return_value.messages.create.return_value = _fake_response(
        {"summary": "ok", "claims": [
            {"text": "real", "sources": ["x1"], "signal_type": "outlier"},
            {"text": "hallucinated", "sources": ["ghost"], "signal_type": "general"},
        ]}
    )
    ws = _seed(db, _user_id(client, auth_headers))

    resp = client.post(f"/workspaces/{ws.id}/brief", headers=auth_headers)
    assert resp.status_code == 200

    row = (
        db.query(AuditLog)
        .filter(AuditLog.workspace_id == ws.id, AuditLog.action == "brief_generated")
        .order_by(AuditLog.created_at.desc())
        .first()
    )
    assert row is not None
    assert row.after_state["claims_dropped"] == 1
    assert row.after_state["claim_count"] == 1
```

> If `AuditLog` has no `created_at` column, drop the `.order_by(...)` (cross-check `backend/app/models/audit.py`); a single brief generation produces one matching row regardless.

- [ ] **Step 6: Run to verify all pass**

Run: `docker-compose run --rm -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test backend pytest tests/test_synthesis_service.py tests/test_briefs_api.py -v`
Expected: PASS — all (existing + the 2 new) green.

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/synthesis_service.py backend/app/routers/briefs.py backend/tests/test_synthesis_service.py backend/tests/test_briefs_api.py
git commit -m "feat: count + audit dropped (invalid-citation) brief claims"
```

---

## Task 2: ClaudeCallLog wiring for synthesis

**Files:**
- Modify: `backend/app/services/synthesis_service.py` (add `_log_synthesis_call`, update `_synthesize` + `synthesize_brief`)
- Test: `backend/tests/test_synthesis_service.py`

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_synthesis_service.py`:

```python
from unittest.mock import MagicMock


@patch("app.database.SessionLocal")
def test_log_synthesis_call_writes_brief_synthesis_row(mock_sessionlocal):
    from app.services.synthesis_service import _log_synthesis_call

    mock_db = MagicMock()
    mock_sessionlocal.return_value = mock_db
    resp = SimpleNamespace(
        usage=SimpleNamespace(input_tokens=3, output_tokens=4),
        content=[SimpleNamespace(text="abc")],
    )
    _log_synthesis_call("ws1", 120, 500, response=resp)

    added = mock_db.add.call_args.args[0]
    assert added.call_type == "brief_synthesis"
    assert added.workspace_id == "ws1"
    assert added.input_tokens == 3 and added.output_tokens == 4
    assert added.prompt_chars == 500
    assert added.success is True
    mock_db.commit.assert_called_once()


@patch("app.services.synthesis_service._log_synthesis_call")
@patch("app.services.claude_client.get_client")
def test_synthesize_brief_logs_synthesis_call(mock_get_client, mock_log, db):
    ws, _, _ = _seed_workspace(db)
    mock_get_client.return_value.messages.create.return_value = _fake_response(
        {"summary": "s", "claims": []}
    )
    synthesize_brief(ws.id, db)

    assert mock_log.called
    assert mock_log.call_args.args[0] == ws.id  # workspace_id is first arg
```

- [ ] **Step 2: Run to verify they fail**

Run: `docker-compose run --rm -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test backend pytest tests/test_synthesis_service.py::test_log_synthesis_call_writes_brief_synthesis_row tests/test_synthesis_service.py::test_synthesize_brief_logs_synthesis_call -v`
Expected: FAIL — `cannot import name '_log_synthesis_call'` / `_log_synthesis_call` not called.

- [ ] **Step 3: Add `_log_synthesis_call` and wire `_synthesize`**

In `backend/app/services/synthesis_service.py`, add this helper right after `_SYNTHESIS_SYSTEM`:

```python
def _log_synthesis_call(
    workspace_id: str,
    latency_ms: int,
    prompt_chars: int,
    response=None,
    error_message: str | None = None,
) -> None:
    """Write one brief_synthesis row to claude_call_logs. Opens its own session so
    logging never corrupts the request transaction; swallows all exceptions.
    """
    try:
        from app.database import SessionLocal
        from app.models.claude_call_log import ClaudeCallLog

        db = SessionLocal()
        try:
            usage = getattr(response, "usage", None)
            content = getattr(response, "content", None)
            row = ClaudeCallLog(
                call_type="brief_synthesis",
                workspace_id=workspace_id,
                model=CHAT_MODEL,
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
```

Replace the whole `_synthesize` function with this version (adds `workspace_id`, times the API call, logs success + error, returns `latency_ms` in meta):

```python
def _synthesize(
    evidence: list[Evidence], saliences: list[Salience], workspace_id: str
) -> tuple[dict, dict]:
    """One constrained Claude call. Logs a brief_synthesis row, returns
    (parsed_brief, meta) with latency_ms. Degrades to an empty brief (never
    raises) only on unparseable JSON; a transport error is logged and re-raised.
    """
    payload = {
        "evidence": [
            {
                "id": e.id,
                "document": e.filename,
                "doc_type": e.doc_type,
                "field": e.field_name,
                "value": e.field_value,
            }
            for e in evidence
        ],
        "saliences": [{"type": s.type, "fact": s.description} for s in saliences],
    }
    user_content = json.dumps(payload)
    prompt_chars = len(_SYNTHESIS_SYSTEM) + len(user_content)

    start = time.perf_counter()
    try:
        response = claude_client.get_client().messages.create(
            model=CHAT_MODEL,
            max_tokens=2048,
            system=_SYNTHESIS_SYSTEM,
            messages=[{"role": "user", "content": user_content}],
        )
    except Exception as e:
        latency_ms = int((time.perf_counter() - start) * 1000)
        _log_synthesis_call(workspace_id, latency_ms, prompt_chars, error_message=str(e))
        raise
    latency_ms = int((time.perf_counter() - start) * 1000)
    _log_synthesis_call(workspace_id, latency_ms, prompt_chars, response=response)

    usage = getattr(response, "usage", None)
    meta = {
        "model": CHAT_MODEL,
        "input_tokens": getattr(usage, "input_tokens", None),
        "output_tokens": getattr(usage, "output_tokens", None),
        "latency_ms": latency_ms,
    }
    try:
        parsed = json.loads(strip_json_fences(response.content[0].text))
    except Exception as e:
        logger.warning(f"Brief synthesis returned unparseable JSON: {e}")
        parsed = {"summary": "", "claims": []}
    return parsed, meta
```

Update `synthesize_brief` — it no longer times the call itself; pass `workspace_id` and use `meta["latency_ms"]`. Replace the block:

```python
    start = time.perf_counter()
    raw, meta = _synthesize(evidence, saliences)
    meta["latency_ms"] = int((time.perf_counter() - start) * 1000)

    brief = _validate_and_annotate(raw, evidence)
    brief.update(meta)
    return brief
```

with:

```python
    raw, meta = _synthesize(evidence, saliences, workspace_id)

    brief = _validate_and_annotate(raw, evidence)
    brief.update(meta)
    return brief
```

- [ ] **Step 4: Run to verify they pass**

Run: `docker-compose run --rm -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test backend pytest tests/test_synthesis_service.py -v`
Expected: PASS — all (the existing end-to-end test still asserts `brief["latency_ms"] is not None`, now sourced from meta; the 2 new tests pass).

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/synthesis_service.py backend/tests/test_synthesis_service.py
git commit -m "feat: log brief synthesis to claude_call_logs (observability + metering)"
```

---

## Task 3: Citation-resolve endpoints

**Files:**
- Modify: `backend/app/routers/briefs.py`
- Test: `backend/tests/test_briefs_api.py`

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_briefs_api.py`:

```python
def test_resolve_citation_returns_source(client, auth_headers, db):
    ws = _seed(db, _user_id(client, auth_headers))  # seeds extraction id "x1"
    resp = client.get(f"/workspaces/{ws.id}/brief/citations/x1", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["extraction_id"] == "x1"
    assert body["field_name"] == "sale_amount"
    assert body["field_value"] == "500000"
    assert "evidence" in body  # region capture (None when not set)


def test_resolve_citation_404_for_unknown(client, auth_headers, db):
    ws = _seed(db, _user_id(client, auth_headers))
    resp = client.get(f"/workspaces/{ws.id}/brief/citations/nope", headers=auth_headers)
    assert resp.status_code == 404


def test_resolve_citations_batch(client, auth_headers, db):
    ws = _seed(db, _user_id(client, auth_headers))
    resp = client.post(
        f"/workspaces/{ws.id}/brief/citations",
        headers=auth_headers,
        json={"extraction_ids": ["x1", "ghost"]},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 1
    assert "x1" in body["resolved"] and "ghost" not in body["resolved"]


def test_resolve_citation_is_workspace_scoped(client, auth_headers, db):
    # x1 belongs to workspace A; resolving it through workspace B must 404.
    ws_a = _seed(db, _user_id(client, auth_headers))  # owns extraction "x1"
    ws_b = _seed(db, _user_id(client, auth_headers))  # same user is a member
    assert ws_a.id != ws_b.id
    resp = client.get(f"/workspaces/{ws_b.id}/brief/citations/x1", headers=auth_headers)
    assert resp.status_code == 404
```

> Note: `_seed` inserts a `DocumentExtraction` with id `"x1"`. Calling `_seed` twice creates two workspaces; the second insert reuses id `"x1"` for its own extraction — that's a PK collision. To make the scoping test work, change `_seed` to accept an optional `ext_id` (default `"x1"`) so the two workspaces use different extraction ids. Update the `_seed` signature: `def _seed(db, owner_user_id, ext_id="x1"):` and use `id=ext_id` on the `DocumentExtraction`. Then in `test_resolve_citation_is_workspace_scoped`, seed B with `ext_id="x2"`. The point still holds: `x1` (workspace A's id) must not resolve under workspace B.

Apply that `_seed` tweak now, and set the scoping test's second seed to `_seed(db, _user_id(client, auth_headers), ext_id="x2")`.

- [ ] **Step 2: Run to verify they fail**

Run: `docker-compose run --rm -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test backend pytest tests/test_briefs_api.py -k resolve -v`
Expected: FAIL — routes not found (404 for wrong reason / method not allowed).

- [ ] **Step 3: Add the resolve endpoints to the router**

In `backend/app/routers/briefs.py`, add imports at the top:

```python
from pydantic import BaseModel

from app.models.document import Document
from app.models.document_extraction import DocumentExtraction
```

Add the request model after the imports (before `router = ...` or just after `_serialize`):

```python
class CitationBatchRequest(BaseModel):
    extraction_ids: list[str]


def _resolve_citation(workspace_id: str, extraction_id: str, db: Session) -> dict | None:
    """Resolve one extraction id to its source detail, scoped to the workspace.
    Returns None if the id is not an extraction in this workspace.
    """
    row = (
        db.query(DocumentExtraction, Document.filename, Document.detected_doc_type)
        .join(Document, Document.id == DocumentExtraction.document_id)
        .filter(
            DocumentExtraction.id == extraction_id,
            DocumentExtraction.workspace_id == workspace_id,
            Document.is_deleted == False,  # noqa: E712
        )
        .first()
    )
    if not row:
        return None
    ext = row.DocumentExtraction
    return {
        "extraction_id": ext.id,
        "document_id": ext.document_id,
        "filename": row.filename,
        "doc_type": row.detected_doc_type,
        "field_name": ext.field_name,
        "field_value": ext.field_value,
        "confidence": ext.confidence,
        "evidence": ext.evidence,  # base64 PNG region capture JSON, or None
    }
```

Add the two endpoints (after `brief_history`):

```python
@router.get("/brief/citations/{extraction_id}")
def resolve_citation(
    workspace_id: str,
    extraction_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    get_workspace_or_404(workspace_id, user, db)
    resolved = _resolve_citation(workspace_id, extraction_id, db)
    if not resolved:
        raise HTTPException(status_code=404, detail="Citation not found in this workspace")
    return resolved


@router.post("/brief/citations")
def resolve_citations(
    workspace_id: str,
    payload: CitationBatchRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    get_workspace_or_404(workspace_id, user, db)
    resolved = {}
    for eid in payload.extraction_ids:
        r = _resolve_citation(workspace_id, eid, db)
        if r:
            resolved[eid] = r
    return {"resolved": resolved, "count": len(resolved)}
```

- [ ] **Step 4: Run to verify they pass**

Run: `docker-compose run --rm -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test backend pytest tests/test_briefs_api.py -v`
Expected: PASS — all (existing + the 4 new resolve tests).

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/briefs.py backend/tests/test_briefs_api.py
git commit -m "feat: citation-resolve endpoints (single + batch, workspace-scoped)"
```

---

## Task 4: Full suite + lint gate

**Files:** none (verification only)

- [ ] **Step 1: Run the CI-collected suite**

Run: `docker-compose run --rm -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test backend pytest tests/ --ignore=tests/evals -q`
Expected: PASS — the prior 264 plus the new tests, no regressions.

- [ ] **Step 2: Run ruff (host)**

Run: `ruff check backend/app backend/tests` (or the host path). Fix anything in the changed files, re-run.

- [ ] **Step 3: Commit any lint fixes**

```bash
git add -A
git commit -m "chore: ruff clean for brief observability + citation resolution"
```
(Skip if ruff reported nothing.)

---

## Done criteria
- `_validate_and_annotate` returns `claims_dropped`; the `brief_generated` audit entry records `claims_dropped` and `claim_count`; a warning logs when claims are dropped.
- `_synthesize` writes a `brief_synthesis` row to `claude_call_logs` (success + transport-error paths) with tokens/latency/prompt_chars; metering's token sums include it automatically.
- `GET /workspaces/{id}/brief/citations/{extraction_id}` resolves a citation to `{document_id, filename, doc_type, field_name, field_value, confidence, evidence}`, 404 when absent; `POST /workspaces/{id}/brief/citations` resolves a batch; both are membership-gated and workspace-scoped (a foreign extraction id does not resolve).
- Full suite green; ruff clean.

## Notes for the implementer
- **No migration** — no schema change. `claims_dropped` lives in the audit log, not a `briefs` column (deliberate).
- **Cross-DB logging:** `_log_synthesis_call` opens its own `SessionLocal` (the app DB, not the test DB) and swallows exceptions — exactly like `extraction_engine._log_claude_call`. Tests therefore patch `_log_synthesis_call` (wiring) or `app.database.SessionLocal` (row shape) rather than asserting against the test session.
- **Don't touch the eval harness or `test_deed_extraction.py`** — these changes are additive; the eval reads `brief["claims"]`/`["summary"]` and is unaffected by the extra `claims_dropped` key.

## Follow-up (out of scope)
- **Frontend "Case Brief" panel** — consumes the `POST .../brief/citations` batch endpoint to render clickable-to-source claims. The remaining user-facing piece; its own brainstorm + plan.
