# Phase 1 — Server-Side Security Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close four server-side security gaps (H6 weak signing key, M1 CSV injection, M2 header injection, M3 upload allowlist + safe serving) from the 2026-05-29 audit, in one reviewable PR.

**Architecture:** All changes live at the HTTP boundary — a new pure-function utils module (`app/utils/sanitize.py`), a config validator (`app/config.py`), and hardening of the documents router. No schema, model, or pipeline-ordering changes. The SHA-256-first invariant and background pipeline are untouched.

**Tech Stack:** Python 3.12, FastAPI, Starlette responses, Pydantic v2 / pydantic-settings, pytest, Docker Compose.

---

## CRITICAL: test run command

After Task 2, `app.config` rejects a missing/weak `SECRET_KEY` **at import time**, so the test container must always receive a strong key or pytest can't even collect. Use this exact command (single line — Windows/PowerShell friendly) for **all** test runs in this plan. `<target>` is the file/test path for the step.

```
docker-compose run --rm -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test -e SECRET_KEY=ci-test-secret-key-please-change-0123456789abcdef backend pytest <target> -v
```

(`ci-test-secret-key-please-change-0123456789abcdef` is 48 chars and not a known-weak literal, so it passes the Task 2 validator. Including it from Task 1 onward is harmless and keeps every command uniform.)

## File structure

- **Create** `backend/app/utils/sanitize.py` — pure HTTP-boundary sanitizers: `escape_csv_cell`, `safe_header_filename`, `content_disposition`. One responsibility: make untrusted strings safe to put in CSV cells and response headers.
- **Create** `backend/tests/test_sanitize.py` — unit tests for the above.
- **Create** `backend/tests/test_config.py` — unit tests for the `SECRET_KEY` validator.
- **Modify** `backend/app/config.py` — add `secret_key` field validator.
- **Modify** `docker-compose.yml` — remove the insecure default for `SECRET_KEY`.
- **Modify** `backend/.env.example` — replace the placeholder with a generate-it instruction.
- **Modify** `backend/app/routers/documents.py` — CSV escaping (M1), safe Content-Disposition (M2), upload allowlist + safe serving (M3).
- **Modify** `backend/tests/test_documents.py` — integration tests for M1/M2/M3.

---

## Task 1: Sanitization utilities

**Files:**
- Create: `backend/app/utils/sanitize.py`
- Test: `backend/tests/test_sanitize.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_sanitize.py`:

```python
from app.utils.sanitize import escape_csv_cell, safe_header_filename, content_disposition


def test_escape_csv_cell_neutralizes_formula_triggers():
    assert escape_csv_cell("=cmd()") == "'=cmd()"
    assert escape_csv_cell("+1+1") == "'+1+1"
    assert escape_csv_cell("-2") == "'-2"
    assert escape_csv_cell("@SUM(A1)") == "'@SUM(A1)"
    assert escape_csv_cell("\tx") == "'\tx"


def test_escape_csv_cell_passes_safe_values():
    assert escape_csv_cell("John Smith") == "John Smith"
    assert escape_csv_cell("285000") == "285000"


def test_escape_csv_cell_handles_none():
    assert escape_csv_cell(None) == ""


def test_safe_header_filename_strips_crlf_and_quotes():
    out = safe_header_filename('evil\r\nSet-Cookie: x".pdf')
    assert "\r" not in out
    assert "\n" not in out
    assert '"' not in out


def test_safe_header_filename_empty_fallback():
    assert safe_header_filename("") == "download"
    assert safe_header_filename("\r\n") == "download"


def test_content_disposition_crlf_free_with_both_params():
    value = content_disposition("a\r\nb.csv", "attachment")
    assert "\r" not in value
    assert "\n" not in value
    assert value.startswith("attachment;")
    assert "filename=" in value
    assert "filename*=UTF-8''" in value


def test_content_disposition_inline_type():
    value = content_disposition("report.pdf", "inline")
    assert value.startswith("inline;")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker-compose run --rm -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test -e SECRET_KEY=ci-test-secret-key-please-change-0123456789abcdef backend pytest tests/test_sanitize.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.utils.sanitize'`.

- [ ] **Step 3: Write the implementation**

Create `backend/app/utils/sanitize.py`:

```python
"""
Shared sanitization helpers for the HTTP boundary.

escape_csv_cell()      — neutralizes spreadsheet formula injection in CSV exports.
safe_header_filename() — strips control chars so filenames can't inject HTTP headers.
content_disposition()  — builds a CRLF-safe Content-Disposition with ASCII + RFC 5987 names.
"""
from urllib.parse import quote

# Leading characters that trigger formula evaluation in Excel / Google Sheets.
_CSV_FORMULA_TRIGGERS = ("=", "+", "-", "@", "\t", "\r")


def escape_csv_cell(value) -> str:
    """Return value as a CSV-safe string, neutralizing formula injection.

    If the stringified value begins with a formula trigger (= + - @ tab CR),
    prefix it with a single quote so spreadsheet apps treat it as text.
    None becomes an empty string.
    """
    if value is None:
        return ""
    text = str(value)
    if text and text[0] in _CSV_FORMULA_TRIGGERS:
        return "'" + text
    return text


def safe_header_filename(name: str) -> str:
    """Return an ASCII-safe filename fragment for a Content-Disposition header.

    Removes control characters (including CR/LF), double quotes, and backslashes
    that could break out of the quoted filename parameter or inject a header.
    Falls back to "download" if nothing usable remains.
    """
    if not name:
        return "download"
    cleaned = "".join(c for c in name if c.isprintable() and c not in '"\\')
    cleaned = cleaned.strip()
    return cleaned or "download"


def content_disposition(filename: str, disposition: str = "attachment") -> str:
    """Build a CRLF-safe Content-Disposition header value.

    Emits both an ASCII `filename="..."` (control-stripped) and an RFC 5987
    `filename*=UTF-8''<percent-encoded>` so user-controlled names cannot inject
    headers while still round-tripping unicode where the client supports it.
    """
    ascii_name = safe_header_filename(filename)
    encoded = quote(filename or "download", safe="")
    return f"{disposition}; filename=\"{ascii_name}\"; filename*=UTF-8''{encoded}"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `docker-compose run --rm -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test -e SECRET_KEY=ci-test-secret-key-please-change-0123456789abcdef backend pytest tests/test_sanitize.py -v`
Expected: PASS (8 tests).

- [ ] **Step 5: Commit**

```
git add backend/app/utils/sanitize.py backend/tests/test_sanitize.py
git commit -m "feat: add sanitize utils (csv escaping, safe content-disposition)"
```

---

## Task 2: Enforce a strong SECRET_KEY (H6)

**Files:**
- Modify: `backend/app/config.py`
- Modify: `docker-compose.yml`
- Modify: `backend/.env.example`
- Test: `backend/tests/test_config.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_config.py`:

```python
import pytest
from pydantic import ValidationError

from app.config import Settings


def _make(**overrides):
    base = dict(
        database_url="postgresql://catalyst:catalyst@localhost:5432/catalyst",
        secret_key="k" * 48,
        anthropic_api_key="sk-ant-test",
    )
    base.update(overrides)
    return Settings(**base)


def test_strong_secret_key_accepted():
    s = _make(secret_key="k" * 48)
    assert s.secret_key == "k" * 48


def test_empty_secret_key_rejected():
    with pytest.raises(ValidationError):
        _make(secret_key="")


def test_known_weak_secret_keys_rejected():
    with pytest.raises(ValidationError):
        _make(secret_key="dev-secret-key-change-in-production")
    with pytest.raises(ValidationError):
        _make(secret_key="change-this-to-a-long-random-string-in-production")


def test_short_secret_key_rejected():
    with pytest.raises(ValidationError):
        _make(secret_key="tooshort")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker-compose run --rm -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test -e SECRET_KEY=ci-test-secret-key-please-change-0123456789abcdef backend pytest tests/test_config.py -v`
Expected: FAIL — weak/short/empty keys are currently accepted, so the `pytest.raises` assertions fail.

- [ ] **Step 3: Add the validator**

Replace the entire contents of `backend/app/config.py` with:

```python
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Placeholder values shipped in docker-compose / .env.example that must never
# be used as a real signing key.
_WEAK_SECRET_KEYS = {
    "dev-secret-key-change-in-production",
    "change-this-to-a-long-random-string-in-production",
}
_MIN_SECRET_KEY_LENGTH = 32


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    database_url: str
    secret_key: str
    anthropic_api_key: str
    upload_dir: str = "./uploads"
    access_token_expire_minutes: int = 60 * 24
    cors_origins: list[str] = ["http://localhost:5173"]
    max_upload_bytes: int = 52_428_800  # 50 MB

    @field_validator("secret_key")
    @classmethod
    def secret_key_must_be_strong(cls, v: str) -> str:
        """Reject empty, placeholder, or short signing keys at startup.

        A weak SECRET_KEY lets anyone forge JWTs for any user, so we fail fast
        rather than boot with a guessable key.
        """
        candidate = (v or "").strip()
        if not candidate:
            raise ValueError("SECRET_KEY must be set (see backend/.env.example)")
        if candidate in _WEAK_SECRET_KEYS:
            raise ValueError(
                "SECRET_KEY is a known placeholder. Generate a strong key: "
                'python -c "import secrets; print(secrets.token_urlsafe(48))"'
            )
        if len(candidate) < _MIN_SECRET_KEY_LENGTH:
            raise ValueError(
                f"SECRET_KEY must be at least {_MIN_SECRET_KEY_LENGTH} characters"
            )
        return v


settings = Settings()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `docker-compose run --rm -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test -e SECRET_KEY=ci-test-secret-key-please-change-0123456789abcdef backend pytest tests/test_config.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Remove the insecure default in `docker-compose.yml`**

In `docker-compose.yml`, under the `backend` service `environment:` block, change:

```yaml
      SECRET_KEY: ${SECRET_KEY:-dev-secret-key-change-in-production}
```

to:

```yaml
      SECRET_KEY: ${SECRET_KEY:?SECRET_KEY must be set - see backend/.env.example}
```

- [ ] **Step 6: Update `backend/.env.example`**

In `backend/.env.example`, replace this line:

```
SECRET_KEY=change-this-to-a-long-random-string-in-production
```

with:

```
# Generate a strong key: python -c "import secrets; print(secrets.token_urlsafe(48))"
SECRET_KEY=
```

- [ ] **Step 7: Verify the full suite still collects and passes with a strong key**

Run: `docker-compose run --rm -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test -e SECRET_KEY=ci-test-secret-key-please-change-0123456789abcdef backend pytest tests/ -v`
Expected: PASS (all existing tests + the new config/sanitize tests). This confirms the import-time validator doesn't break collection when a strong key is supplied.

- [ ] **Step 8: Commit**

```
git add backend/app/config.py backend/tests/test_config.py docker-compose.yml backend/.env.example
git commit -m "fix(security): enforce strong SECRET_KEY at startup (H6)"
```

---

## Task 3: Escape CSV formula injection in exports (M1)

**Files:**
- Modify: `backend/app/routers/documents.py`
- Test: `backend/tests/test_documents.py`

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_documents.py`:

```python
def test_export_csv_escapes_formula_injection(client, auth_headers, workspace_id, db):
    import io as io_module
    from unittest.mock import patch
    from app.models.document import Document
    from app.models.document_extraction import DocumentExtraction

    with patch("app.routers.documents.process_upload_background"):
        doc_id = client.post(
            f"/workspaces/{workspace_id}/documents",
            files={"file": ("inj.pdf", io_module.BytesIO(b"%PDF-1.4 x"), "application/pdf")},
            headers=auth_headers,
        ).json()["id"]

    doc = db.query(Document).filter(Document.id == doc_id).first()
    doc.extraction_status = "complete"
    db.flush()
    db.add(DocumentExtraction(
        document_id=doc_id, workspace_id=workspace_id,
        field_name="payee", field_value="=2+5+cmd",
        field_type="text", confidence=0.9, attempt=1,
    ))
    db.commit()

    res = client.get(
        f"/workspaces/{workspace_id}/documents/{doc_id}/extractions.csv",
        headers=auth_headers,
    )
    assert res.status_code == 200
    assert "'=2+5+cmd" in res.text          # neutralized with a leading quote
    assert "payee,=2+5+cmd" not in res.text  # never written as a bare formula
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker-compose run --rm -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test -e SECRET_KEY=ci-test-secret-key-please-change-0123456789abcdef backend pytest tests/test_documents.py::test_export_csv_escapes_formula_injection -v`
Expected: FAIL — the value is written bare (`payee,=2+5+cmd`).

- [ ] **Step 3: Apply escaping in both CSV writers**

In `backend/app/routers/documents.py`, add to the imports near the top:

```python
from app.utils.sanitize import escape_csv_cell
```

In `download_extractions_csv`, change the per-row write to escape every cell:

```python
    for e in extractions:
        writer.writerow({
            "field_name": escape_csv_cell(e.field_name),
            "field_value": escape_csv_cell(e.field_value),
            "field_type": escape_csv_cell(e.field_type),
            "confidence": e.confidence,
            "attempt": e.attempt,
        })
```

In `download_workspace_extractions_csv`, change the per-row write the same way:

```python
        for e in _latest_extractions(doc.id, db):
            writer.writerow({
                "document_filename": escape_csv_cell(doc.filename),
                "document_type": escape_csv_cell(doc.detected_doc_type or ""),
                "field_name": escape_csv_cell(e.field_name),
                "field_value": escape_csv_cell(e.field_value),
                "field_type": escape_csv_cell(e.field_type),
                "confidence": e.confidence,
                "attempt": e.attempt,
            })
```

- [ ] **Step 4: Run test to verify it passes**

Run: `docker-compose run --rm -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test -e SECRET_KEY=ci-test-secret-key-please-change-0123456789abcdef backend pytest tests/test_documents.py -v`
Expected: PASS (new test + existing export tests unaffected).

- [ ] **Step 5: Commit**

```
git add backend/app/routers/documents.py backend/tests/test_documents.py
git commit -m "fix(security): escape CSV formula injection in exports (M1)"
```

---

## Task 4: Sanitize Content-Disposition filenames (M2)

**Files:**
- Modify: `backend/app/routers/documents.py`
- Test: `backend/tests/test_documents.py`

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_documents.py`:

```python
def test_export_csv_filename_header_has_no_crlf(client, auth_headers, workspace_id, db):
    import io as io_module
    from unittest.mock import patch
    from app.models.document import Document

    with patch("app.routers.documents.process_upload_background"):
        doc_id = client.post(
            f"/workspaces/{workspace_id}/documents",
            files={"file": ("hdr.pdf", io_module.BytesIO(b"%PDF-1.4 x"), "application/pdf")},
            headers=auth_headers,
        ).json()["id"]

    doc = db.query(Document).filter(Document.id == doc_id).first()
    doc.filename = "evil\r\nSet-Cookie: pwned.pdf"
    doc.extraction_status = "complete"
    db.commit()

    res = client.get(
        f"/workspaces/{workspace_id}/documents/{doc_id}/extractions.csv",
        headers=auth_headers,
    )
    assert res.status_code == 200
    cd = res.headers["content-disposition"]
    assert "\r" not in cd
    assert "\n" not in cd
    assert cd.startswith("attachment;")
    assert "filename*=UTF-8''" in cd   # only the fixed code emits RFC 5987 form
    assert "set-cookie" not in res.headers
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker-compose run --rm -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test -e SECRET_KEY=ci-test-secret-key-please-change-0123456789abcdef backend pytest tests/test_documents.py::test_export_csv_filename_header_has_no_crlf -v`
Expected: FAIL — current code uses `doc.filename.replace('"','')`, leaving CR/LF in the header (the ASGI server may also raise on the bad header).

- [ ] **Step 3: Use the safe header builder in both per-document exports**

First, extend the sanitize import added in Task 3 to include `content_disposition`:

```python
from app.utils.sanitize import content_disposition, escape_csv_cell
```

In `download_extractions_csv`, replace:

```python
    safe_name = doc.filename.replace('"', '')
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}_extractions.csv"'},
    )
```

with:

```python
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": content_disposition(f"{doc.filename}_extractions.csv", "attachment")},
    )
```

In `download_extractions_json`, replace:

```python
    safe_name = doc.filename.replace('"', '')
    return Response(
        content=json_module.dumps(data, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}_extractions.json"'},
    )
```

with:

```python
    return Response(
        content=json_module.dumps(data, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": content_disposition(f"{doc.filename}_extractions.json", "attachment")},
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `docker-compose run --rm -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test -e SECRET_KEY=ci-test-secret-key-please-change-0123456789abcdef backend pytest tests/test_documents.py -v`
Expected: PASS (new test + existing tests, including `test_export_json_returns_json`, still green).

- [ ] **Step 5: Commit**

```
git add backend/app/routers/documents.py backend/tests/test_documents.py
git commit -m "fix(security): sanitize Content-Disposition filenames (M2)"
```

---

## Task 5: Upload allowlist + safe file serving (M3)

**Files:**
- Modify: `backend/app/routers/documents.py`
- Test: `backend/tests/test_documents.py`

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_documents.py`:

```python
def test_upload_rejects_disallowed_extension(client, auth_headers, workspace_id):
    res = client.post(
        f"/workspaces/{workspace_id}/documents",
        files={"file": ("evil.exe", io.BytesIO(b"MZ\x90\x00"), "application/octet-stream")},
        headers=auth_headers,
    )
    assert res.status_code == 415


def test_upload_allows_allowed_extension(client, auth_headers, workspace_id):
    from unittest.mock import patch
    with patch("app.routers.documents.process_upload_background"):
        res = client.post(
            f"/workspaces/{workspace_id}/documents",
            files={"file": ("ok.pdf", io.BytesIO(b"%PDF-1.4 x"), "application/pdf")},
            headers=auth_headers,
        )
    assert res.status_code == 201


def test_served_pdf_is_inline_with_nosniff(client, auth_headers, workspace_id):
    from unittest.mock import patch
    with patch("app.routers.documents.process_upload_background"):
        doc_id = client.post(
            f"/workspaces/{workspace_id}/documents",
            files={"file": ("doc.pdf", io.BytesIO(b"%PDF-1.4 x"), "application/pdf")},
            headers=auth_headers,
        ).json()["id"]
    res = client.get(
        f"/workspaces/{workspace_id}/documents/{doc_id}/file",
        headers=auth_headers,
    )
    assert res.status_code == 200
    assert res.headers["x-content-type-options"] == "nosniff"
    assert res.headers["content-disposition"].startswith("inline")


def test_served_csv_is_attachment(client, auth_headers, workspace_id):
    from unittest.mock import patch
    with patch("app.routers.documents.process_upload_background"):
        doc_id = client.post(
            f"/workspaces/{workspace_id}/documents",
            files={"file": ("data.csv", io.BytesIO(b"a,b\n1,2\n"), "text/csv")},
            headers=auth_headers,
        ).json()["id"]
    res = client.get(
        f"/workspaces/{workspace_id}/documents/{doc_id}/file",
        headers=auth_headers,
    )
    assert res.status_code == 200
    assert res.headers["x-content-type-options"] == "nosniff"
    assert res.headers["content-disposition"].startswith("attachment")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker-compose run --rm -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test -e SECRET_KEY=ci-test-secret-key-please-change-0123456789abcdef backend pytest tests/test_documents.py::test_upload_rejects_disallowed_extension tests/test_documents.py::test_served_pdf_is_inline_with_nosniff tests/test_documents.py::test_served_csv_is_attachment -v`
Expected: FAIL — `.exe` currently returns 201; served files have no `nosniff` header and use Starlette's default disposition.

- [ ] **Step 3a: Add the allowlist constant + import**

In `backend/app/routers/documents.py`, extend the existing `document_pipeline` import to include the extension map and add the inline-suffix set near the existing `_MEDIA_TYPES` constant:

```python
from app.services.document_pipeline import (
    EXTENSION_TO_TYPE,
    create_pending_document,
    process_upload_background,
)

ALLOWED_UPLOAD_EXTENSIONS = set(EXTENSION_TO_TYPE)
INLINE_SUFFIXES = {".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".tif"}
```

- [ ] **Step 3b: Enforce the allowlist in `upload_document`**

In `upload_document`, immediately after the empty-file and size checks (after the `413` raise), add:

```python
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_UPLOAD_EXTENSIONS:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type '{ext or '(none)'}'. Accepted: "
                   f"{', '.join(sorted(ALLOWED_UPLOAD_EXTENSIONS))}",
        )
```

- [ ] **Step 3c: Harden `get_document_file`**

In `get_document_file`, replace the final two lines:

```python
    media_type = _MEDIA_TYPES.get(file_path.suffix.lower(), "application/octet-stream")
    return FileResponse(str(file_path), media_type=media_type)
```

with:

```python
    suffix = file_path.suffix.lower()
    media_type = _MEDIA_TYPES.get(suffix, "application/octet-stream")
    disposition = "inline" if suffix in INLINE_SUFFIXES else "attachment"
    return FileResponse(
        str(file_path),
        media_type=media_type,
        headers={
            "X-Content-Type-Options": "nosniff",
            "Content-Disposition": content_disposition(doc.original_filename, disposition),
        },
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `docker-compose run --rm -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test -e SECRET_KEY=ci-test-secret-key-please-change-0123456789abcdef backend pytest tests/test_documents.py -v`
Expected: PASS — including the existing `test_get_document_file` (still 200, now `inline` + `nosniff`) and `test_get_document_file_not_found` (still 404).

- [ ] **Step 5: Commit**

```
git add backend/app/routers/documents.py backend/tests/test_documents.py
git commit -m "fix(security): enforce upload allowlist and safe file serving (M3)"
```

---

## Final verification

- [ ] **Run the full backend suite**

Run: `docker-compose run --rm -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test -e SECRET_KEY=ci-test-secret-key-please-change-0123456789abcdef backend pytest tests/ -v`
Expected: all tests pass.

- [ ] **Confirm fail-fast behavior manually (optional sanity check)**

Run: `docker-compose run --rm -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test -e SECRET_KEY=dev-secret-key-change-in-production backend python -c "import app.main"`
Expected: FAIL at import with the SECRET_KEY validation error (proves H6 blocks a weak key at startup).

---

## Notes for the implementer

- **Don't refactor the router beyond these changes.** Moving export/serve logic into a service is M5 / Phase 5, intentionally deferred.
- **The `process_upload_background` patch** in the new tests keeps them hermetic — it prevents the background pipeline from making real OCR/Claude calls. Existing tests are left as-is.
- **`Path` and `Response`/`FileResponse`** are already imported in `documents.py`; no new stdlib imports needed there beyond the `sanitize` helpers.
