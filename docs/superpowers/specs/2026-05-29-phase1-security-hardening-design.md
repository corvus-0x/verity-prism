# Phase 1 — Server-Side Security Hardening (Design Spec)

**Date:** 2026-05-29
**Branch:** `feat/phase-1-security-hardening`
**Source:** `docs/code-audit-2026-05-29.md` findings H6, M1, M2, M3
**Status:** Approved (design), pending implementation plan

---

## Goal

Close four server-side security gaps that don't depend on schema/migration changes, in one coherent, reviewable PR. This is the first of six sequenced phases that together resolve the full audit. None of these fixes require migration-only DDL, so the existing `create_all`-based test setup is sufficient (migrations-in-tests is Phase 2).

## Scope

In scope: H6, M1, M2, M3 (below).
Explicitly **out of scope** (deferred to later phases):
- Moving export/file-serve logic out of routers into services → M5 / Phase 5.
- JWT `localStorage` → httpOnly cookie migration → M6 / Phase 6.
- Deep upload content/magic-byte validation → future hardening; Phase 1 enforces an extension allowlist only.

## Decisions (approved)

- **(A) H6 strictness:** fail-fast. Reject empty, known-weak literals, and keys `< 32` chars at startup. Local dev must set a real key once.
- **(B) M3 policy:** allowlist = `{pdf, png, jpg, jpeg, tiff, tif, csv, txt, xml}`; reject unknown extensions with `415`. Serve PDFs/images **inline** (DocumentViewer needs it), everything else as `attachment`. Always send `X-Content-Type-Options: nosniff`.

---

## Components

### New: `backend/app/utils/sanitize.py`
Shared, pure, unit-testable helpers (mirrors the style of `utils/json_helpers.py`).

- `escape_csv_cell(value: str | None) -> str`
  - Returns `""` for `None`.
  - If the stringified value's first character is one of `= + - @`, TAB (`\t`), or CR (`\r`), prefix the result with a single quote `'` (OWASP CSV-injection neutralization).
  - Otherwise return the string unchanged.
- `safe_header_filename(name: str) -> str`
  - Strip CR/LF and other control characters.
  - Produce an ASCII-safe fallback (non-allowlisted chars → removed/replaced), used for the legacy `filename=` parameter.
  - Caller emits RFC 5987 `filename*=UTF-8''<percent-encoded>` alongside the ASCII fallback.

### H6 — Weak default signing key
- `docker-compose.yml`: change `SECRET_KEY: ${SECRET_KEY:-dev-secret-key-change-in-production}` → `SECRET_KEY: ${SECRET_KEY:?SECRET_KEY must be set (see backend/.env.example)}`.
- `backend/app/config.py`: add a Pydantic `field_validator` on `secret_key`:
  - reject empty / whitespace-only,
  - reject known weak literals: `dev-secret-key-change-in-production`, `change-this-to-a-long-random-string-in-production`,
  - reject `len < 32`,
  - raise `ValueError` with a clear remediation message (fails app startup).
- `backend/.env.example`: replace the placeholder line with a generate-it instruction, e.g.
  `# Generate: python -c "import secrets; print(secrets.token_urlsafe(48))"`
  `SECRET_KEY=`

### M1 — CSV/formula injection
- `backend/app/routers/documents.py`: in both CSV writers
  (`download_extractions_csv`, `download_workspace_extractions_csv`) route every written cell value (`field_name`, `field_value`, `document_filename`, `document_type`, etc.) through `escape_csv_cell`. The two JSON exports are not modified (JSON is not formula-injectable).

### M2 — Header/filename injection
- `backend/app/routers/documents.py`: replace `safe_name = doc.filename.replace('"', '')` in the two **per-document** export endpoints (`download_extractions_csv`, `download_extractions_json`) with `safe_header_filename(...)`, emitting a `Content-Disposition` using both `filename="<ascii>"` and `filename*=UTF-8''<encoded>`. The two **workspace** exports already use static filenames (`workspace_extractions.csv/json`) and need no change.

### M3 — Upload allowlist + safe serving
- Upload (`upload_document` in `routers/documents.py`): compute the extension; if it is not in the allowlist, raise `415 Unsupported Media Type` before hashing/storing. (Allowlist sourced from the existing `EXTENSION_TO_TYPE` keys, excluding the `"other"` catch-all.)
- Serve (`get_document_file`): always set header `X-Content-Type-Options: nosniff`; set `Content-Disposition: inline` for pdf/png/jpg/jpeg/tiff/tif, `attachment` otherwise.

---

## Data flow (unchanged)
No schema, model, or pipeline-ordering changes. All edits are at the HTTP boundary (routers + config) plus one new utils module. The SHA-256-first invariant is untouched; the allowlist check happens before `create_pending_document`.

## Error handling
- Invalid `SECRET_KEY` → app refuses to start with an actionable message (intended).
- Disallowed upload → `415` with a message listing accepted types; nothing written to disk or DB.
- Sanitization helpers never raise on normal input; `None`/empty handled explicitly.

## Testing (TDD, red → green)
All in the existing `create_all` test DB.

1. **config validator** (`test_config.py`, new): weak literal / short / empty `secret_key` raises; a 48-char key passes. Implemented as a direct `Settings(...)` construction test so it doesn't depend on env.
2. **M1** (`test_documents.py`): export a document whose `field_value` is `=cmd()` → the CSV cell is `'=cmd()`.
3. **M2** (`test_documents.py`): a document whose filename contains `\r\n` → response `Content-Disposition` contains no raw CR/LF.
4. **M3 upload** (`test_documents.py`): uploading `evil.exe` → `415`; uploading an allowed type still → `201`.
5. **M3 serve** (`test_documents.py`): file response includes `X-Content-Type-Options: nosniff`; a `.pdf` is `inline`, a `.csv` is `attachment`.

## Acceptance criteria
- All new + existing backend tests pass.
- App fails to boot with a weak/short `SECRET_KEY`; boots with a strong one.
- No CSV export cell can begin with a bare formula trigger.
- No `Content-Disposition` header can contain attacker-controlled CR/LF.
- Disallowed extensions are rejected at upload; served files carry `nosniff` and the correct disposition.

## Out-of-scope acknowledgements (carried to later phases)
M5 (router thinness), M6 (cookie auth), and deeper content-type/magic-byte validation are intentionally not addressed here.
