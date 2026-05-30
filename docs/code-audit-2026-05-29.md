# Verity Prism — Code Audit

**Date:** 2026-05-29
**Scope:** Backend services (auth, document_pipeline, extraction_engine, ai_engine, agent_tools, search_service, audit, ocr, xml_parser, naming, extraction_evaluator); routers auth/documents/ai/workspaces/search/audit; core models; config; all Alembic migrations; docker-compose; tests for auth/documents/ai/agent_tools; frontend auth/api/chat/stream/context.
**Not audited (silence ≠ clean):** routers and services for entities, findings, leads, notes, review, transactions, schemas; most frontend pages/components. "Missing auth dependency" and "mutation skips audit" were only checked on the routers above.
**Auditor:** Opus 4.8 (max effort)

---

## Executive summary

The architecture is sound and the workspace-isolation model is genuinely well built — `workspace_id` injection in the AI engine fails safe, and membership is checked on every workspace route. But the platform's **single most important promise is fiction**: the "immutable audit log" enforced by a PostgreSQL trigger **does not exist** — no migration ever creates it, yet CLAUDE.md and the `audit.py` docstring both assert it as a database-level guarantee. For an evidence-handling platform, that is the finding to fix first. Close behind: a Claude API outage silently marks documents `complete` with **zero extracted fields** (evidence loss that looks like success), full-text search and the AI assistant **surface data from soft-deleted documents**, and the extraction engine only ever reads the **first 4000 characters** of any document. The test suite cannot catch most of this because it builds the schema with `create_all` and **never runs the migrations**, so every migration-only guarantee (the audit trigger, enum values, the FTS column) is untested.

**Fix first:** Create and test the `audit_log` immutability trigger, then stop the pipeline from reporting `complete` on empty/failed extraction.

---

## Critical findings — fix before any real case data

### C1 — The immutable audit-log trigger does not exist ✅ RESOLVED (Phase 2 — migration `3f29a7ad2392`)
**Files:** `backend/alembic/versions/5a4ff7266708_initial_schema.py:79-93` (table created, no trigger); entire `backend/alembic/versions/` (no trigger anywhere); claim asserted in `backend/app/services/audit.py:19-21` and `CLAUDE.md`.

`audit_log` is created as an ordinary table. The trigger is **confirmed absent from every place it could live**: no migration creates it (grep for `CREATE TRIGGER`/`BEFORE UPDATE`/`BEFORE DELETE`/`audit_log_immutable`/`CREATE FUNCTION` across `backend/` → nothing); there are **no `.sql` files anywhere** in the repo; and `docker-compose.yml`'s `db` service mounts **no** `docker-entrypoint-initdb.d` init script (only the data volume). The trigger DDL exists in exactly two places: the original plan (`docs/superpowers/plans/2026-05-17-phase1-backend-api.md:882`) and CLAUDE.md's claim that it's done. **It was specified, documented as built, and never implemented.** The immutability that `audit.py`'s docstring describes as a database-level control is enforced by **nothing** — any `UPDATE`/`DELETE` (accidental, malicious, or a future buggy cascade) will succeed. In an evidence context this is the difference between an audit trail and a suggestion.

**Fix:** Add a migration that creates a `BEFORE UPDATE OR DELETE ON audit_log` trigger calling a function that `RAISE EXCEPTION`s. Add a test (run against a migrated DB, not `create_all`) that asserts `UPDATE audit_log` and `DELETE FROM audit_log` both raise. Until tests run migrations (H3), this guarantee remains unverifiable.

```sql
CREATE OR REPLACE FUNCTION audit_log_immutable() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'audit_log is immutable: % blocked', TG_OP;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER audit_log_immutable
BEFORE UPDATE OR DELETE ON audit_log
FOR EACH ROW EXECUTE FUNCTION audit_log_immutable();
```

### C2 — Claude outage marks documents `complete` with zero fields (silent evidence loss)
**Files:** `extraction_engine.py:254-268` (`_extract_batch` swallows all errors, returns `[]`); `extraction_engine.py:271-309` (`extract_fields` merges empty batches); `document_pipeline.py:222-234, 292-293`; `extraction_evaluator.py:30-45` (`evaluate([])` → `needs_review=False`).

When every Claude extraction call fails (API down, rate-limited, network), each batch returns `[]`. `extract_fields` returns `[]`, `save_extractions([])` writes nothing, and because the evaluator's `low_confidence_fields` list is empty for an empty input, `needs_review` is `False`. The pipeline then sets `extraction_status = "complete"`. **A document with no extracted data is indistinguishable from a successfully processed one.** For evidence, a false "complete" is worse than a visible "failed."

**Fix:** Distinguish "Claude returned no fields" from "Claude call failed." Have `_extract_batch` signal failure (raise, or return a sentinel) separately from a genuine empty result; if any batch failed, set status `failed` (or a new `extraction_incomplete`) with the error. At minimum, if a `claude` schema yields zero saved fields, never mark `complete`.

---

## High findings — fix before any external user

### H1 — Search and AI surface data from soft-deleted documents
**Files:** `search_service.py:96` (`run_search` base query has no `is_deleted` filter); `search_service.py:158-163` (direct-fetch branch also unfiltered); `agent_tools.py:99-107` (`query_extractions` joins `Document` but never filters `Document.is_deleted`).

`Document` has `is_deleted`/`deleted_at` (model `document.py:40-41`, migration `a3b8e1f9`). `search_documents` correctly filters it (`agent_tools.py:28`), but `run_search` and `query_extractions` do not. So a document an investigator soft-deleted — wrong case, privileged, inadmissible — still has its extracted fields returned by plain-English search and quoted by the AI assistant. This borders on Critical for a legal/evidence workflow.

**Fix:** Add `Document.is_deleted == False` to the base query in `run_search` (both branches) and join-filter it in `query_extractions`. Consider a query helper so "active documents" is defined once.

### H2 — `search_vector` is the wrong column type with no index
**Files:** `models/document.py:31` (`Mapped[str] ... Text`); migration `5a4ff7266708_initial_schema.py:107` (`sa.Text()`); populated as a tsvector in `document_pipeline.py:314-320`; queried with `@@` in `search_service.py:100-104` and `agent_tools.py:32-35`.

`search_vector` is declared `TEXT` but the pipeline stores `to_tsvector('english', …)` into it and queries it with `@@ plainto_tsquery(...)`. Postgres tolerates `text @@ tsquery` by *re-running* `to_tsvector` over the **stored serialized tsvector string** (e.g. `'word':1 'other':2`) on every row, every query. The result: matching is semantically wrong (it tokenizes lexeme/position markers), there is **no GIN index** so every search is a sequential scan, and relevance is unreliable. It "works" on a handful of test rows by coincidence.

**Fix:** Change the column to `TSVECTOR` (`sqlalchemy.dialects.postgresql.TSVECTOR`), add a migration that alters the type and creates a `GIN` index, and ideally make it a generated column or trigger-maintained. Re-point the pipeline to write the tsvector directly.

### H3 — Tests never run migrations, so migration-only guarantees are untested ✅ RESOLVED (Phase 2)
**File:** `tests/conftest.py:17-21` (`Base.metadata.create_all` / `drop_all`).

The test DB is built from the ORM models, not from Alembic. Everything that lives only in migrations is therefore absent in tests and **cannot be verified**: the (missing) audit trigger (C1), the `no_schema`/`needs_review` enum values, and any DDL drift between models and migrations. This is *why* C1 went unnoticed — there is no test that could have caught it. It also means production and test schemas can silently diverge.

**Fix:** Run `alembic upgrade head` against the test DB in a session-scoped fixture instead of `create_all`. Keep per-test data isolation via truncation or transactional rollback. Then add the C1 trigger test.

### H4 — The extraction pipeline has effectively no test coverage
**Files:** `tests/test_documents.py:12-23` (accepts any `extraction_status`); no test files for `document_pipeline`, `extraction_engine`, `search_service`, `ocr`, `xml_parser`, `naming`, `extraction_evaluator`.

`test_upload_creates_document_record` asserts `extraction_status in ("pending","complete","failed","no_schema")` — i.e. it passes no matter what the pipeline does. The upload tests don't mock Claude; they rely on `fitz.open` failing on the fake PDF bytes so the pipeline dies at OCR and never reaches Claude. That's fragile (a real PDF in a fixture would hit the live API and bill it) and means the core IDP path — type detection, schema match, extraction, evaluation, retry, indexing — is exercised by nothing. This is the heart of the product.

**Fix:** Add pipeline tests that patch the Claude clients (`extraction_engine.client`, etc.), feed known OCR text, and assert specific extracted fields, status transitions, and the no-schema/lead path. Assert *outcomes*, not "any of four statuses."

### H5 — Extraction only reads the first 4000 characters of a document
**File:** `extraction_engine.py:216` (`Document text:\n{ocr_text[:4000]}`).

Batching splits the *field list* across calls, but every batch sees the **same truncated first 4000 characters** of OCR text. Any field whose value appears later in a multi-page deed, a 235-field 990, or a 370-field parcel record can never be extracted — directly contradicting the platform's "extract every data point" premise. Type detection (`[:1500]`, line 130) and naming (`[:1500]`) are fine for their purposes; extraction is not.

**Fix:** Window the text per batch, or chunk long documents and run extraction per chunk, or pass the full relevant span. At minimum, log/flag when `len(ocr_text)` exceeds the cap so silent truncation is visible.

### H6 — Weak default JWT signing key in docker-compose (token forgery)
**Files:** `docker-compose.yml:21` (`SECRET_KEY: ${SECRET_KEY:-dev-secret-key-change-in-production}`); consumed by `services/auth.py:28,40` via `config.py:8`.

`config.py` correctly requires `secret_key` with no default — but docker-compose supplies the fallback `dev-secret-key-change-in-production` whenever the env var is unset. If the stack is deployed without explicitly setting `SECRET_KEY`, every JWT is signed with a **publicly known string**, so anyone can forge a valid token for any `user_id` and fully bypass authentication. This is Critical-if-deployed-as-is; it's ranked High because it requires the operator to skip setting the var — which the silent default makes easy.

**Fix:** Remove the insecure fallback (let the container fail fast if `SECRET_KEY` is unset), or generate a strong key at deploy time. Add a startup assertion that rejects known/short keys. Do the same for any deployment manifests beyond compose.

---

## Medium findings — fix before v1 launch

### M1 — CSV/formula injection in exports
**Files:** `routers/documents.py:276-283, 309-318, 347-357, 381-391`.

`field_value` is written verbatim to exported CSV. Values come from OCR of uploaded (attacker-influenced) documents. A value beginning with `=`, `+`, `-`, or `@` becomes a live formula when the investigator opens the CSV in Excel/Sheets (data exfiltration, command execution via DDE). 

**Fix:** Prefix cells beginning with `= + - @ \t \r` with a single quote, or quote/escape per OWASP CSV-injection guidance.

### M2 — Header injection / unsanitized filename in `Content-Disposition`
**Files:** `routers/documents.py:285, 319` (`safe_name = doc.filename.replace('"','')`); fallback path `naming.py:56,59` returns `f"...{original_filename}"`.

`doc.filename` is normally the regex-sanitized standardized name, but when naming **falls back** it embeds the raw `original_filename`, which is user-controlled and only has `"` stripped — CR/LF and other bytes survive, allowing response-header injection. 

**Fix:** Sanitize to a strict allowlist (`[^\w\-.]` → removed) and/or use Starlette's `Content-Disposition` filename encoding. Never interpolate raw upload names into headers.

### M3 — No upload type allowlist; files served without anti-sniffing headers
**Files:** `document_pipeline.py:109-116` (any extension stored; unknown → `"other"`); `routers/documents.py:411-449` (`get_document_file` serves with a guessed media type, no `X-Content-Type-Options: nosniff`, no forced `attachment`).

Any extension is accepted. An uploaded `.html`/`.svg` served back without `nosniff` can be MIME-sniffed by the browser into stored XSS in the app's origin. 

**Fix:** Enforce an allowlist of accepted types at upload; on the file route send `X-Content-Type-Options: nosniff` and `Content-Disposition: attachment` for anything not explicitly inline-safe.

### M4 — Audit gaps on failures and on auth events ✅ RESOLVED (Phase 2)
**Files:** `document_pipeline.py:55-60` (`_fail` writes no audit), `:188,195,233` (failure returns skip audit); `routers/auth.py:11-30` (register/login unaudited); `routers/ai.py:16-27` (`create_conversation` unaudited).

A failed evidence upload leaves **no audit record at all**. Authentication events (login success/failure, registration) are not audited — for a forensic platform, who-accessed-what-when should include auth. 

**Fix:** Write an audit row on every terminal pipeline state including failures; audit login (success and failure) and registration. (Once C1 is fixed these records are actually immutable.)

### M5 — Business logic in routers; router imports another router
**Files:** `routers/documents.py:88-169` (SSE generator with latest-attempt subquery), `:234-397` (CSV/JSON building, `_latest_extractions`); `routers/documents.py:17` and `routers/ai.py:7` and others `from app.routers.workspaces import get_workspace_or_404`.

CLAUDE.md mandates thin routers (validate → call service → return). The document router contains real logic (export construction, the streaming query). `get_workspace_or_404` is an authz helper living in a *router* and imported by other routers — it belongs in a deps/service module. Nearly every router also queries models directly rather than via a service.

**Fix:** Move export and streaming logic into `document_pipeline`/a new `export_service`; move `get_workspace_or_404` into `app/deps.py` or a workspace service; route reads through services where practical.

### M6 — Frontend stores the JWT in localStorage
**File:** `frontend/src/store/auth.js:4-14` (zustand `persist`, default `localStorage`).

`localStorage` is readable by any script in the origin, so any XSS (see M3) can exfiltrate the token. 

**Fix:** Prefer an httpOnly, Secure, SameSite cookie set by the backend; if staying with SPA-managed tokens, minimize blast radius (short-lived access token + refresh, strict CSP).

### M7 — Frontend swallows API errors
**Files:** `pages/workspace/AIChat.jsx:20-25,31-35,37-42,44-61` (no `catch`); `context/WorkspaceContext.jsx:11-14` (no `catch`).

`handleSend` has `try/finally` but no `catch`: if the message POST fails, the optimistic user bubble (`id:'temp'`) stays on screen, "Thinking…" disappears, and the user is told nothing. Initial conversation load and workspace load fail silently (blank UI, `workspace` stuck `null`). 

**Fix:** Add `catch` branches that surface a toast/error state and roll back the optimistic message on failure.

### M8 — Commit-without-rollback leaves sessions poisoned
**Files:** `services/audit.py:36-37`, `document_pipeline.py:59,199,217,293`, various routers.

Services call `db.commit()` with no `try/except … rollback()`. If a commit fails (constraint, connection blip), the session enters a failed state; the next operation — including `_fail()`'s own `commit()` — also fails, so the document can't even be marked failed. `get_db` only closes; it never rolls back.

**Fix:** Wrap commits with rollback on exception (or add a rollback in the `get_db` finally path and a transactional helper in the pipeline). Ensure `_fail` uses a clean transaction.

---

## Low findings / polish

- **L1 — `get_conversation_history` not workspace-scoped.** `ai_engine.py:27-40` filters only by `conversation_id`. The router validates ownership first, so this is defense-in-depth only; add a `workspace_id` filter anyway.
- **L2 — SSE reader not cancelled on unmount.** `hooks/useExtractionStream.js:68-71` sets a `cancelled` flag but never calls `reader.cancel()`; the fetch/connection lingers until the next 2s tick or the server's 5-min timeout.
- **L3 — Orphaned files on pipeline failure.** `document_pipeline.py:116` writes the file before OCR; failures leave the file on disk with no cleanup.
- **L4 — Hard redirect on 401.** `api/client.js:23` uses `window.location.href`, discarding SPA state; prefer router navigation.
- **L5 — Soft-delete pattern is inconsistent.** Only `Document` and `Entity` have `is_deleted`; `Transaction`, `Finding`, `InvestigationLead`, `Note`, `Relationship` do not. "Soft delete everywhere" is aspirational, not implemented — decide and apply consistently (this also means the agent tools for those types correctly have no `is_deleted` filter today).
- **L6 — Module-level `Anthropic()` clients.** Four services instantiate the client at import (`extraction_engine`, `ai_engine`, `search_service`, `naming`); a missing API key fails at import. Only `ai_engine.client` is patched in tests. Consider a shared lazily-constructed client.

---

## Coverage map

| Service file | Has tests | Critical paths covered | Notes |
|---|---|---|---|
| `services/auth.py` | Indirect (`test_auth.py`) | Partial | Register/login/wrong-password/no-token covered. No unit tests for expired/invalid/tampered JWT or `get_current_user` user-missing path. |
| `services/ai_engine.py` | Yes (`test_ai.py`) | Good | Tool loop, synthesis pass, text extraction, multi-turn dedup. Client correctly patched at `app.services.ai_engine.client`. |
| `services/agent_tools.py` | Yes (`test_agent_tools.py`) | Good | All six tools, workspace isolation, soft-delete on entity, overpay math. Does **not** catch the `Document.is_deleted` gap in `query_extractions` (H1). |
| `services/document_pipeline.py` | **No** | None | Upload endpoint tests tolerate any status and rely on OCR failing (H4). |
| `services/extraction_engine.py` | **No** | None | No batch/normalize/merge tests; truncation (H5) untested. |
| `services/extraction_evaluator.py` | **No** | None | `evaluate()` is pure and trivially testable; the empty-input → `needs_review=False` behavior (C2) is untested. |
| `services/search_service.py` | **No** | None | Translate + run_search untested; H1/H2 uncaught. |
| `services/ocr.py` | **No** | None | No PDF/image/text-path tests. |
| `services/xml_parser.py` | **No** | None | Path extraction / namespace handling untested. |
| `services/naming.py` | **No** | None | Fallback path (M2) untested. |
| `services/audit.py` | **No** | None | No test that the trigger blocks mutation (can't exist until H3). |
| Routers (documents/search/audit/workspaces) | Partial | Partial | Endpoint happy paths via TestClient; export injection (M1) and error paths uncovered. |

---

## Design invariant checklist

| # | Invariant | Status | Evidence |
|---|---|---|---|
| 1 | SHA-256 hash computed first | ✓ Holds | `document_pipeline.py:107` hashes before disk write (`:116`) and before the DB row (`:118-131`); OCR/extraction run later in the background. |
| 2 | Soft deletes everywhere; active records filtered | ✗ Violated (partial) | `run_search` (`search_service.py:96,158`) and `query_extractions` (`agent_tools.py:99-107`) don't filter `Document.is_deleted` (H1). Pattern only exists on `Document`+`Entity` (L5). |
| 3 | Audit log immutable (PG trigger); `audit.log()` after every action | ✗ Violated | **No trigger exists** in any migration (C1). Failed uploads and auth events write no audit (M4). |
| 4 | Routers thin | ✗ Violated | Export/SSE logic in `routers/documents.py` (M5); routers query models directly; `get_workspace_or_404` lives in a router and is cross-imported. |
| 5 | `workspace_id` injected by dispatcher, never Claude-settable | ✓ Holds (robust) | `agent_tools.execute()` (`:248`) passes `workspace_id=` explicitly; if Claude's `params` also contained `workspace_id`, the call raises `TypeError` and is caught → fails safe, no cross-workspace leak. |
| 6 | Claude mocked in tests via `app.services.ai_engine.client` | ⚠ Partial | Correct in `test_ai.py`. But `extraction_engine`/`search_service`/`naming` have separate module-level clients that no test patches; pipeline tests neither mock nor assert (H4). |

---

## Remediation phases

| Phase | Findings | Theme | Status |
|---|---|---|---|
| 1 | H6, M1, M2, M3 | Server-side security hardening | ✅ Done — merged 2026-05-29 |
| 2 | H3 → C1, M4 | Test infra + audit-log integrity | ✅ Done — merged 2026-05-29 |
| 3 | H4 → C2, H5, L3 | Extraction pipeline correctness | ✅ Done — merged 2026-05-29 |
| 4 | H1, H2, L5, L1 | Search & soft-delete data integrity | — |
| 5 | M5, L6 | Architecture refactor (thin routers, lazy client) | — |
| 6 | M6, M7, L2, L4 | Frontend resilience + JWT hardening | — |

**Phase 3 detail:** ✅ Write mocked-Claude pipeline tests (H4) first — they're the safety net for C2 (false-`complete` on empty extraction) and H5 (4000-char truncation). L3 = orphaned file cleanup on pipeline failure.

**Phase 4 detail:** H1 (soft-delete filters in `run_search` / `query_extractions`) and H2 (`search_vector` column type → `TSVECTOR` + GIN index) are the two most user-visible correctness gaps. L5 = extend soft-delete pattern to Transaction/Finding/Lead. L1 = workspace-scope `get_conversation_history`.

**Phase 5 detail:** M5 = move `get_workspace_or_404` to `app/deps.py`, export/SSE logic to services. L6 = lazy module-level Anthropic client. Refactor clean code, not buggy — do after Phase 4.

**Phase 6 detail:** M6 = httpOnly cookie migration (touches both backend auth and frontend store — largest single change). M7 = frontend error handling. L2 = SSE reader cancel on unmount. L4 = router navigation on 401.

---

## Suggested fix order

✅ Phase 1 complete: H6, M1, M2, M3
✅ Phase 2 complete: H3, C1, M4
✅ Phase 3 complete: H4, C2, H5, L3

Remaining open findings (Phases 4–6):

1. **C2** stop reporting `complete` on failed/empty extraction.
2. **H1** soft-delete filters in search/AI; **H5** extraction text window.
3. **H4** real pipeline tests with mocked Claude.
4. **H2** `tsvector` + GIN index.
5. **M5** thin routers (router refactor).
6. **M6** JWT → httpOnly cookie + frontend resilience (M7, L2, L4).
