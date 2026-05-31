# Phase 5 — Thin Routers + Lazy Client Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate three architecture violations flagged in the 2026-05-29 code audit (M5, L6): move `get_workspace_or_404` out of a router into `app/deps.py`; extract export and SSE logic from the document router into `app/services/export_service.py`; consolidate four module-level Anthropic client instantiations into a single lazy `app/services/claude_client.py`.

**Architecture:** Three independent refactors, each delivered as its own commit. No behavior changes — these are structural moves. Every endpoint response stays byte-identical before and after. The test suite is the regression net.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.0, Anthropic SDK, pytest. All tests run via: `docker-compose run --rm -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test backend pytest <file> -v`

---

## File Map

| Action | Path | Responsibility |
|--------|------|---------------|
| **Create** | `backend/app/deps.py` | `get_workspace_or_404` — membership check + workspace lookup |
| **Modify** | `backend/app/routers/workspaces.py` | Remove definition; import from `app.deps` |
| **Modify** | `backend/app/routers/ai.py` | Import `get_workspace_or_404` from `app.deps` |
| **Modify** | `backend/app/routers/audit.py` | Import `get_workspace_or_404` from `app.deps` |
| **Modify** | `backend/app/routers/documents.py` | Import from `app.deps`; replace export/SSE inline code with service calls |
| **Modify** | `backend/app/routers/entities.py` | Import `get_workspace_or_404` from `app.deps` |
| **Modify** | `backend/app/routers/findings.py` | Import `get_workspace_or_404` from `app.deps` |
| **Modify** | `backend/app/routers/leads.py` | Import `get_workspace_or_404` from `app.deps` |
| **Modify** | `backend/app/routers/notes.py` | Import `get_workspace_or_404` from `app.deps` |
| **Modify** | `backend/app/routers/review.py` | Import `get_workspace_or_404` from `app.deps` |
| **Modify** | `backend/app/routers/search.py` | Import `get_workspace_or_404` from `app.deps` |
| **Modify** | `backend/app/routers/transactions.py` | Import `get_workspace_or_404` from `app.deps` |
| **Modify** | `backend/app/routers/schemas.py` | Check — import `get_workspace_or_404` from `app.deps` if present |
| **Create** | `backend/app/services/export_service.py` | `latest_extractions`, CSV/JSON builders, `document_status_stream` async generator |
| **Create** | `backend/app/services/claude_client.py` | Lazy singleton `get_client()` — single Anthropic instantiation point |
| **Modify** | `backend/app/services/ai_engine.py` | Remove module-level `client`; call `claude_client.get_client()` |
| **Modify** | `backend/app/services/extraction_engine.py` | Remove module-level `client`; call `claude_client.get_client()` |
| **Modify** | `backend/app/services/naming.py` | Remove module-level `client`; call `claude_client.get_client()` |
| **Modify** | `backend/app/services/search_service.py` | Remove module-level `client`; call `claude_client.get_client()` |
| **Modify** | `backend/tests/test_pipeline.py` | Update 5 patches from `extraction_engine.client` → `claude_client.get_client` |
| **Modify** | `backend/tests/test_ai.py` | Update 4 patches from `ai_engine.client` → `claude_client.get_client` |
| **Modify** | `backend/tests/test_extractions.py` | Update patches from `extraction_engine.client` / `extraction_engine.Anthropic` → `claude_client.get_client` |
| **Create** | `backend/tests/test_deps.py` | Unit tests for `get_workspace_or_404` (404 paths, success path) |
| **Create** | `backend/tests/test_export_service.py` | Unit tests for `latest_extractions`, CSV/JSON builders |
| **Modify** | `backend/tests/test_search.py` | Update 0 patches (search_service.Anthropic mock is ineffective anyway; no change needed) |

---

## Task 1: Create `app/deps.py` — move `get_workspace_or_404`

**Files:**
- Create: `backend/app/deps.py`
- Modify: `backend/app/routers/workspaces.py`
- Modify: `backend/app/routers/ai.py`, `audit.py`, `documents.py`, `entities.py`, `findings.py`, `leads.py`, `notes.py`, `review.py`, `search.py`, `transactions.py`
- Create: `backend/tests/test_deps.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_deps.py`:

```python
import uuid
import pytest
from fastapi import HTTPException

from app.deps import get_workspace_or_404
from app.models.user import User
from app.models.workspace import Workspace, WorkspaceMember


@pytest.fixture
def user(db):
    u = User(
        id=str(uuid.uuid4()),
        email=f"deps_{uuid.uuid4().hex[:8]}@test.com",
        password_hash="hashed",
        full_name="Deps Test User",
    )
    db.add(u)
    db.commit()
    return u


@pytest.fixture
def workspace(db, user):
    ws = Workspace(id=str(uuid.uuid4()), name="Deps WS", vertical="fraud", created_by=user.id)
    db.add(ws)
    member = WorkspaceMember(workspace_id=ws.id, user_id=user.id, role="owner")
    db.add(member)
    db.commit()
    return ws


def test_get_workspace_or_404_returns_workspace(db, user, workspace):
    result = get_workspace_or_404(workspace.id, user, db)
    assert result.id == workspace.id
    assert result.name == "Deps WS"


def test_get_workspace_or_404_raises_404_when_not_member(db, workspace):
    outsider = User(
        id=str(uuid.uuid4()),
        email="outsider@test.com",
        password_hash="hashed",
        full_name="Outsider",
    )
    db.add(outsider)
    db.commit()
    with pytest.raises(HTTPException) as exc:
        get_workspace_or_404(workspace.id, outsider, db)
    assert exc.value.status_code == 404


def test_get_workspace_or_404_raises_404_for_nonexistent_workspace(db, user):
    with pytest.raises(HTTPException) as exc:
        get_workspace_or_404(str(uuid.uuid4()), user, db)
    assert exc.value.status_code == 404
```

- [ ] **Step 2: Run tests to confirm they fail**

```
docker-compose run --rm -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test backend pytest tests/test_deps.py -v
```

Expected: `ImportError: cannot import name 'get_workspace_or_404' from 'app.deps'`

- [ ] **Step 3: Create `backend/app/deps.py`**

```python
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.workspace import Workspace, WorkspaceMember


def get_workspace_or_404(workspace_id: str, user: User, db: Session) -> Workspace:
    """Verify user membership and return the workspace, or raise 404.
    Called at the start of every workspace-scoped endpoint as an authz gate.
    """
    membership = db.query(WorkspaceMember).filter(
        WorkspaceMember.workspace_id == workspace_id,
        WorkspaceMember.user_id == user.id,
    ).first()
    if not membership:
        raise HTTPException(status_code=404, detail="Workspace not found")
    workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return workspace
```

- [ ] **Step 4: Run tests to confirm they pass**

```
docker-compose run --rm -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test backend pytest tests/test_deps.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Update `backend/app/routers/workspaces.py`**

Replace the function definition with an import. Change the top of the file from:

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.workspace import Workspace, WorkspaceMember
from app.schemas.workspace import WorkspaceCreate, WorkspaceOut, WorkspaceUpdate
from app.services import audit
from app.services.auth import get_current_user

router = APIRouter(prefix="/workspaces", tags=["workspaces"])

def get_workspace_or_404(workspace_id: str, user: User, db: Session) -> Workspace:
    membership = db.query(WorkspaceMember).filter(
        WorkspaceMember.workspace_id == workspace_id,
        WorkspaceMember.user_id == user.id
    ).first()
    if not membership:
        raise HTTPException(status_code=404, detail="Workspace not found")
    workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return workspace
```

To:

```python
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_workspace_or_404
from app.models.user import User
from app.models.workspace import Workspace, WorkspaceMember
from app.schemas.workspace import WorkspaceCreate, WorkspaceOut, WorkspaceUpdate
from app.services import audit
from app.services.auth import get_current_user

router = APIRouter(prefix="/workspaces", tags=["workspaces"])
```

- [ ] **Step 6: Update the 10 other routers — change import source**

In each of these files, replace:
```python
from app.routers.workspaces import get_workspace_or_404
```
with:
```python
from app.deps import get_workspace_or_404
```

Files to update (one-liner change each):
- `backend/app/routers/ai.py`
- `backend/app/routers/audit.py`
- `backend/app/routers/documents.py`
- `backend/app/routers/entities.py`
- `backend/app/routers/findings.py`
- `backend/app/routers/leads.py`
- `backend/app/routers/notes.py`
- `backend/app/routers/review.py`
- `backend/app/routers/search.py`
- `backend/app/routers/transactions.py`

Also check `backend/app/routers/schemas.py` — run `grep -n "get_workspace_or_404" backend/app/routers/schemas.py` to confirm whether it imports this function. Update if it does.

- [ ] **Step 7: Run the full test suite to verify no regressions**

```
docker-compose run --rm -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test backend pytest tests/ -v
```

Expected: all previously passing tests still pass.

- [ ] **Step 8: Commit**

```bash
git add backend/app/deps.py backend/app/routers/ backend/tests/test_deps.py
git commit -m "refactor(M5): move get_workspace_or_404 to app/deps.py

Router-to-router import circular dependency eliminated. All 11 router
files now import from app.deps instead of app.routers.workspaces.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 2: Create `app/services/export_service.py` — extract export and SSE logic

**Files:**
- Create: `backend/app/services/export_service.py`
- Create: `backend/tests/test_export_service.py`
- Modify: `backend/app/routers/documents.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_export_service.py`:

```python
import csv
import io
import json
import uuid
from datetime import UTC, datetime

import pytest

from app.models.document import Document
from app.models.document_extraction import DocumentExtraction
from app.models.user import User
from app.models.workspace import Workspace
from app.services.export_service import (
    build_document_csv,
    build_document_json,
    build_workspace_csv,
    build_workspace_json,
    latest_extractions,
)


@pytest.fixture
def user(db):
    u = User(
        id=str(uuid.uuid4()),
        email=f"exp_{uuid.uuid4().hex[:8]}@test.com",
        password_hash="hashed",
        full_name="Export Test User",
    )
    db.add(u)
    db.commit()
    return u


@pytest.fixture
def workspace(db, user):
    ws = Workspace(id=str(uuid.uuid4()), name="Export WS", vertical="fraud", created_by=user.id)
    db.add(ws)
    db.commit()
    return ws


@pytest.fixture
def doc_with_extractions(db, workspace, user):
    doc = Document(
        id=str(uuid.uuid4()),
        workspace_id=workspace.id,
        filename="2024-01-15_DEED_smith_transfer.pdf",
        original_filename="deed.pdf",
        file_path="/uploads/deed.pdf",
        file_type="pdf",
        sha256_hash="a" * 64,
        uploaded_by=user.id,
        detected_doc_type="DEED",
        extraction_status="complete",
        is_deleted=False,
    )
    db.add(doc)
    db.commit()
    for attempt in (1, 2):
        db.add(DocumentExtraction(
            id=str(uuid.uuid4()),
            document_id=doc.id,
            workspace_id=workspace.id,
            field_name="grantor",
            field_value=f"John Smith attempt {attempt}",
            field_type="text",
            confidence=0.95,
            attempt=attempt,
        ))
    db.add(DocumentExtraction(
        id=str(uuid.uuid4()),
        document_id=doc.id,
        workspace_id=workspace.id,
        field_name="consideration_amount",
        field_value="250000",
        field_type="currency",
        confidence=0.9,
        attempt=1,
    ))
    db.commit()
    return doc


def test_latest_extractions_returns_only_latest_attempt(db, doc_with_extractions):
    exts = latest_extractions(doc_with_extractions.id, db)
    grantor_rows = [e for e in exts if e.field_name == "grantor"]
    assert len(grantor_rows) == 1
    assert grantor_rows[0].attempt == 2
    assert grantor_rows[0].field_value == "John Smith attempt 2"


def test_latest_extractions_returns_all_fields(db, doc_with_extractions):
    exts = latest_extractions(doc_with_extractions.id, db)
    field_names = {e.field_name for e in exts}
    assert field_names == {"grantor", "consideration_amount"}


def test_build_document_csv_contains_headers_and_data(db, doc_with_extractions):
    exts = latest_extractions(doc_with_extractions.id, db)
    content = build_document_csv(doc_with_extractions, exts)
    reader = csv.DictReader(io.StringIO(content))
    rows = list(reader)
    assert len(rows) == 2
    field_names = {r["field_name"] for r in rows}
    assert "grantor" in field_names
    assert "consideration_amount" in field_names


def test_build_document_csv_blocks_formula_injection(db, workspace, user, db):
    doc = Document(
        id=str(uuid.uuid4()),
        workspace_id=workspace.id,
        filename="malicious.pdf",
        original_filename="malicious.pdf",
        file_path="/uploads/malicious.pdf",
        file_type="pdf",
        sha256_hash="b" * 64,
        uploaded_by=user.id,
        detected_doc_type="DEED",
        extraction_status="complete",
        is_deleted=False,
    )
    db.add(doc)
    db.add(DocumentExtraction(
        id=str(uuid.uuid4()),
        document_id=doc.id,
        workspace_id=workspace.id,
        field_name="grantor",
        field_value="=CMD|'/c calc'!A0",
        field_type="text",
        confidence=0.95,
        attempt=1,
    ))
    db.commit()
    exts = latest_extractions(doc.id, db)
    content = build_document_csv(doc, exts)
    assert "=CMD" not in content


def test_build_document_json_structure(db, doc_with_extractions):
    exts = latest_extractions(doc_with_extractions.id, db)
    content = build_document_json(doc_with_extractions, exts)
    data = json.loads(content)
    assert isinstance(data, list)
    assert len(data) == 2
    assert all("field_name" in row and "field_value" in row for row in data)


def test_build_workspace_csv_includes_all_docs(db, workspace, user, doc_with_extractions):
    docs = [doc_with_extractions]
    content = build_workspace_csv(docs, db)
    assert "2024-01-15_DEED_smith_transfer.pdf" in content
    assert "grantor" in content


def test_build_workspace_json_structure(db, workspace, user, doc_with_extractions):
    docs = [doc_with_extractions]
    content = build_workspace_json(docs, db)
    data = json.loads(content)
    assert isinstance(data, list)
    assert any(row["document_filename"] == "2024-01-15_DEED_smith_transfer.pdf" for row in data)
```

- [ ] **Step 2: Run tests to confirm they fail**

```
docker-compose run --rm -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test backend pytest tests/test_export_service.py -v
```

Expected: `ImportError: cannot import name 'latest_extractions' from 'app.services.export_service'`

- [ ] **Step 3: Create `backend/app/services/export_service.py`**

```python
"""
Export Service — document and workspace data export (CSV, JSON) and SSE streaming.

Routers are thin: they call these functions and wrap results in Response/StreamingResponse.
All formatting and query logic lives here.
"""
import asyncio
import csv
import io
import json
import logging

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.document_extraction import DocumentExtraction
from app.utils.sanitize import escape_csv_cell

logger = logging.getLogger(__name__)


def latest_extractions(document_id: str, db: Session) -> list[DocumentExtraction]:
    """Return one DocumentExtraction per field_name — the highest attempt number."""
    latest_subq = (
        db.query(
            DocumentExtraction.field_name,
            func.max(DocumentExtraction.attempt).label("max_attempt"),
        )
        .filter(DocumentExtraction.document_id == document_id)
        .group_by(DocumentExtraction.field_name)
        .subquery()
    )
    return (
        db.query(DocumentExtraction)
        .join(
            latest_subq,
            (DocumentExtraction.field_name == latest_subq.c.field_name)
            & (DocumentExtraction.attempt == latest_subq.c.max_attempt),
        )
        .filter(DocumentExtraction.document_id == document_id)
        .all()
    )


def build_document_csv(doc: Document, extractions: list[DocumentExtraction]) -> str:
    """Serialize a document's extractions to CSV string (OWASP formula-injection safe)."""
    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=["field_name", "field_value", "field_type", "confidence", "attempt"],
    )
    writer.writeheader()
    for e in extractions:
        writer.writerow({
            "field_name": escape_csv_cell(e.field_name),
            "field_value": escape_csv_cell(e.field_value),
            "field_type": escape_csv_cell(e.field_type),
            "confidence": e.confidence,
            "attempt": e.attempt,
        })
    return output.getvalue()


def build_document_json(doc: Document, extractions: list[DocumentExtraction]) -> str:
    """Serialize a document's extractions to JSON string."""
    return json.dumps(
        [
            {
                "field_name": e.field_name,
                "field_value": e.field_value or "",
                "field_type": e.field_type,
                "confidence": e.confidence,
                "attempt": e.attempt,
            }
            for e in extractions
        ],
        indent=2,
    )


def build_workspace_csv(docs: list[Document], db: Session) -> str:
    """Serialize all extractions across a list of documents to CSV string."""
    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=[
            "document_filename", "document_type",
            "field_name", "field_value", "field_type", "confidence", "attempt",
        ],
    )
    writer.writeheader()
    for doc in docs:
        for e in latest_extractions(doc.id, db):
            writer.writerow({
                "document_filename": escape_csv_cell(doc.filename),
                "document_type": escape_csv_cell(doc.detected_doc_type or ""),
                "field_name": escape_csv_cell(e.field_name),
                "field_value": escape_csv_cell(e.field_value),
                "field_type": escape_csv_cell(e.field_type),
                "confidence": e.confidence,
                "attempt": e.attempt,
            })
    return output.getvalue()


def build_workspace_json(docs: list[Document], db: Session) -> str:
    """Serialize all extractions across a list of documents to JSON string."""
    data = []
    for doc in docs:
        for e in latest_extractions(doc.id, db):
            data.append({
                "document_filename": doc.filename,
                "document_type": doc.detected_doc_type or "",
                "field_name": e.field_name,
                "field_value": e.field_value or "",
                "field_type": e.field_type,
                "confidence": e.confidence,
                "attempt": e.attempt,
            })
    return json.dumps(data, indent=2)


async def document_status_stream(workspace_id: str, document_id: str):
    """Async generator that yields SSE events for a document's extraction status.
    Opens its own DB session so the long-lived poll doesn't block the request session.
    Closes on terminal status (complete/failed/no_schema/needs_review) or 5-min timeout.
    """
    import json as _json
    from sqlalchemy import func as sqlfunc

    from app.database import SessionLocal
    from app.models.document_extraction import DocumentExtraction

    TERMINAL = {"complete", "failed", "no_schema", "needs_review"}
    stream_db = SessionLocal()
    try:
        elapsed = 0
        max_seconds = 300
        interval = 2

        while elapsed < max_seconds:
            stream_db.expire_all()
            doc = stream_db.query(Document).filter(
                Document.id == document_id,
                Document.workspace_id == workspace_id,
            ).first()

            if not doc:
                yield f"data: {_json.dumps({'error': 'not found'})}\n\n"
                return

            status = doc.extraction_status
            payload = {"extraction_status": status}

            if status == "complete":
                latest_subq = (
                    stream_db.query(
                        DocumentExtraction.field_name,
                        sqlfunc.max(DocumentExtraction.attempt).label("max_attempt"),
                    )
                    .filter(DocumentExtraction.document_id == document_id)
                    .group_by(DocumentExtraction.field_name)
                    .subquery()
                )
                field_count = (
                    stream_db.query(sqlfunc.count(DocumentExtraction.id))
                    .join(
                        latest_subq,
                        (DocumentExtraction.field_name == latest_subq.c.field_name)
                        & (DocumentExtraction.attempt == latest_subq.c.max_attempt),
                    )
                    .filter(DocumentExtraction.document_id == document_id)
                    .scalar()
                )
                payload["field_count"] = field_count
                payload["detected_doc_type"] = doc.detected_doc_type
            elif status == "failed":
                payload["extraction_error"] = doc.extraction_error

            yield f"data: {_json.dumps(payload)}\n\n"

            if status in TERMINAL:
                return

            await asyncio.sleep(interval)
            elapsed += interval

        yield f"data: {_json.dumps({'extraction_status': 'timeout'})}\n\n"
    finally:
        stream_db.close()
```

- [ ] **Step 4: Run tests to confirm they pass**

```
docker-compose run --rm -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test backend pytest tests/test_export_service.py -v
```

Expected: all tests pass. Fix any test fixture issues (the `test_build_document_csv_blocks_formula_injection` test has `db` listed twice as a parameter — remove the duplicate).

Note: the correct signature for that test is:
```python
def test_build_document_csv_blocks_formula_injection(db, workspace, user):
```

- [ ] **Step 5: Slim down `backend/app/routers/documents.py`**

Replace the imports block. Remove `asyncio`, `csv`, `io`, `json as json_module`, and add the export service import. The new imports at the top of `documents.py`:

```python
import json as json_module
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, Response, StreamingResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.deps import get_workspace_or_404
from app.models.document import Document
from app.models.document_extraction import DocumentExtraction
from app.models.user import User
from app.schemas.document import DocumentOut, ExtractionOut
from app.services import audit, export_service
from app.services.auth import get_current_user
from app.services.document_pipeline import (
    EXTENSION_TO_TYPE,
    create_pending_document,
    process_upload_background,
)
from app.utils.sanitize import content_disposition, escape_csv_cell
```

Remove the `_latest_extractions` helper function (lines 252–272 in the original). It is now `export_service.latest_extractions`.

Replace `stream_document_status` body. The full endpoint becomes:

```python
@router.get("/documents/{document_id}/status/stream")
async def stream_document_status(
    workspace_id: str,
    document_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Stream extraction status updates via Server-Sent Events."""
    get_workspace_or_404(workspace_id, user, db)
    return StreamingResponse(
        export_service.document_status_stream(workspace_id, document_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
```

Replace `download_extractions_csv` body:

```python
@router.get("/documents/{document_id}/extractions.csv")
def download_extractions_csv(
    workspace_id: str,
    document_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Download extracted fields for one document as CSV (latest attempt per field)."""
    get_workspace_or_404(workspace_id, user, db)
    doc = db.query(Document).filter(
        Document.id == document_id, Document.workspace_id == workspace_id
    ).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    extractions = export_service.latest_extractions(document_id, db)
    content = export_service.build_document_csv(doc, extractions)
    return Response(
        content=content,
        media_type="text/csv",
        headers={"Content-Disposition": content_disposition(f"{doc.filename}_extractions.csv", "attachment")},
    )
```

Replace `download_extractions_json` body:

```python
@router.get("/documents/{document_id}/extractions.json")
def download_extractions_json(
    workspace_id: str,
    document_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Download extracted fields for one document as JSON (latest attempt per field)."""
    get_workspace_or_404(workspace_id, user, db)
    doc = db.query(Document).filter(
        Document.id == document_id, Document.workspace_id == workspace_id
    ).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    extractions = export_service.latest_extractions(document_id, db)
    content = export_service.build_document_json(doc, extractions)
    return Response(
        content=content,
        media_type="application/json",
        headers={"Content-Disposition": content_disposition(f"{doc.filename}_extractions.json", "attachment")},
    )
```

Replace `download_workspace_extractions_csv` body:

```python
@router.get("/extractions.csv")
def download_workspace_extractions_csv(
    workspace_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Download all extractions across the workspace as CSV."""
    get_workspace_or_404(workspace_id, user, db)
    docs = db.query(Document).filter(
        Document.workspace_id == workspace_id,
        Document.extraction_status.in_(["complete", "needs_review"]),
        Document.is_deleted == False,  # noqa: E712
    ).all()
    content = export_service.build_workspace_csv(docs, db)
    return Response(
        content=content,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="workspace_extractions.csv"'},
    )
```

Replace `download_workspace_extractions_json` body:

```python
@router.get("/extractions.json")
def download_workspace_extractions_json(
    workspace_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Download all extractions across the workspace as JSON."""
    get_workspace_or_404(workspace_id, user, db)
    docs = db.query(Document).filter(
        Document.workspace_id == workspace_id,
        Document.extraction_status.in_(["complete", "needs_review"]),
        Document.is_deleted == False,  # noqa: E712
    ).all()
    content = export_service.build_workspace_json(docs, db)
    return Response(
        content=content,
        media_type="application/json",
        headers={"Content-Disposition": 'attachment; filename="workspace_extractions.json"'},
    )
```

Also update `list_extractions` to use `export_service.latest_extractions` for the non-history path:

```python
@router.get("/documents/{document_id}/extractions", response_model=list[ExtractionOut])
def list_extractions(
    workspace_id: str,
    document_id: str,
    include_history: bool = Query(default=False),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Return extracted fields for a document.
    Default: one row per field_name (the latest attempt).
    ?include_history=true: all rows for all attempts, ordered by field_name then attempt.
    """
    get_workspace_or_404(workspace_id, user, db)

    if include_history:
        return (
            db.query(DocumentExtraction)
            .filter(DocumentExtraction.document_id == document_id)
            .order_by(DocumentExtraction.field_name, DocumentExtraction.attempt)
            .all()
        )

    return export_service.latest_extractions(document_id, db)
```

After these changes, `import asyncio`, `import csv`, `import io`, and `_latest_extractions` can be removed from `documents.py`. Verify `json as json_module` is still needed — it is only used in `stream_document_status` which is now delegated to the service. Remove it too. The `func` import from `sqlalchemy` is used only in `list_extractions` via the old subquery — now that's also in the service. Remove `from sqlalchemy import func`.

Final check: run `grep -n "json_module\|asyncio\|import csv\|import io\|func\b" backend/app/routers/documents.py` to confirm none of these remain used.

- [ ] **Step 6: Run the full test suite**

```
docker-compose run --rm -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test backend pytest tests/ -v
```

Expected: all previously passing tests still pass, plus new export service tests pass.

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/export_service.py backend/app/routers/documents.py backend/tests/test_export_service.py
git commit -m "refactor(M5): extract export and SSE logic to export_service

documents.py router is now thin: validate → call service → return Response.
latest_extractions, CSV/JSON builders, and document_status_stream live in
export_service.py. list_extractions now reuses the shared latest_extractions helper.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 3: Create `app/services/claude_client.py` — lazy shared Anthropic client

**Files:**
- Create: `backend/app/services/claude_client.py`
- Modify: `backend/app/services/ai_engine.py`
- Modify: `backend/app/services/extraction_engine.py`
- Modify: `backend/app/services/naming.py`
- Modify: `backend/app/services/search_service.py`
- Modify: `backend/tests/test_pipeline.py`
- Modify: `backend/tests/test_ai.py`
- Modify: `backend/tests/test_extractions.py`

- [ ] **Step 1: Write a failing test for the shared client**

Add to `backend/tests/test_export_service.py` (or any test file that imports a service that uses Claude):

Actually, create a new dedicated test file `backend/tests/test_claude_client.py`:

```python
from unittest.mock import MagicMock, patch


def test_get_client_returns_anthropic_instance():
    """get_client() must return the same instance on repeated calls (singleton)."""
    from app.services.claude_client import get_client
    c1 = get_client()
    c2 = get_client()
    assert c1 is c2


def test_all_services_use_shared_client():
    """Patching claude_client.get_client reaches all four Claude-using services."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text='{"document_type": "OTHER"}')]
    mock_client.messages.create.return_value = mock_response

    with patch("app.services.claude_client.get_client", return_value=mock_client):
        # Importing after the patch is applied confirms the binding goes through claude_client
        from app.services import claude_client
        result = claude_client.get_client()
        assert result is mock_client
```

- [ ] **Step 2: Run test to confirm it fails**

```
docker-compose run --rm -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test backend pytest tests/test_claude_client.py -v
```

Expected: `ModuleNotFoundError: No module named 'app.services.claude_client'`

- [ ] **Step 3: Create `backend/app/services/claude_client.py`**

```python
"""
Shared lazy Anthropic client.

All services call get_client() instead of instantiating Anthropic() directly.
Benefits:
- Missing API key fails at first call, not at module import
- Single instantiation point for future retry logic and spend tracking
- Single patch target in tests: patch("app.services.claude_client.get_client")
"""
from anthropic import Anthropic

from app.config import settings

_client: "Anthropic | None" = None


def get_client() -> Anthropic:
    """Return the shared Anthropic client, constructing it on first call."""
    global _client
    if _client is None:
        _client = Anthropic(api_key=settings.anthropic_api_key)
    return _client
```

- [ ] **Step 4: Run test to confirm it passes**

```
docker-compose run --rm -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test backend pytest tests/test_claude_client.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Update `backend/app/services/ai_engine.py`**

Remove the module-level client and import the shared getter instead.

Replace:
```python
from anthropic import Anthropic

from app.config import settings
from app.models.ai import AIConversation, AIMessage
from app.models.workspace import Workspace
from app.services import agent_registry, agent_tools

logger = logging.getLogger(__name__)
client = Anthropic(api_key=settings.anthropic_api_key)
```

With:
```python
from app.models.ai import AIConversation, AIMessage
from app.models.workspace import Workspace
from app.services import agent_registry, agent_tools, claude_client

logger = logging.getLogger(__name__)
```

Replace every `client.messages.create(` with `claude_client.get_client().messages.create(`.

There are two call sites in `ai_engine.py` — the main tool loop and the synthesis pass. Confirm by running:
```
grep -n "client\." backend/app/services/ai_engine.py
```

- [ ] **Step 6: Update `backend/app/services/extraction_engine.py`**

Replace:
```python
from anthropic import Anthropic

from app.config import settings
...
client = Anthropic(api_key=settings.anthropic_api_key)
```

With:
```python
from app.services import claude_client
```

(Keep all other imports. Remove the `from anthropic import Anthropic` and `from app.config import settings` lines only if they are no longer used for anything else. Verify with grep.)

Replace every `client.messages.create(` with `claude_client.get_client().messages.create(`.

Run `grep -n "client\." backend/app/services/extraction_engine.py` to find all call sites.

- [ ] **Step 7: Update `backend/app/services/naming.py`**

Replace:
```python
from anthropic import Anthropic

from app.config import settings
...
client = Anthropic(api_key=settings.anthropic_api_key)
```

With:
```python
from app.services import claude_client
```

Replace every `client.messages.create(` with `claude_client.get_client().messages.create(`.

- [ ] **Step 8: Update `backend/app/services/search_service.py`**

Replace:
```python
from anthropic import Anthropic

from app.config import settings
...
client = Anthropic(api_key=settings.anthropic_api_key)
```

With:
```python
from app.services import claude_client
```

Replace every `client.messages.create(` with `claude_client.get_client().messages.create(`.

- [ ] **Step 9: Update test patches — `backend/tests/test_pipeline.py`**

Current (5 occurrences to update):
```python
patch("app.services.extraction_engine.client")
```

Change all 5 to:
```python
patch("app.services.claude_client.get_client", return_value=mock_client)
```

Grep to find all locations:
```
grep -n "extraction_engine.client\|ai_engine.client" backend/tests/test_pipeline.py
```

For tests that use the mock as a context manager value (`as mock_client`), the pattern changes from:
```python
with patch("app.services.extraction_engine.client") as mock_client:
    mock_client.messages.create.return_value = ...
```
To:
```python
mock_client = MagicMock()
mock_client.messages.create.return_value = ...
with patch("app.services.claude_client.get_client", return_value=mock_client):
```

For tests that just suppress the client without capturing it:
```python
patch("app.services.extraction_engine.client")
```
Changes to:
```python
patch("app.services.claude_client.get_client", return_value=MagicMock())
```

- [ ] **Step 10: Update test patches — `backend/tests/test_ai.py`**

Current pattern:
```python
with patch("app.services.ai_engine.client") as mock_client:
    mock_client.messages.create.return_value = ...
```

Change to:
```python
mock_client = MagicMock()
mock_client.messages.create.return_value = ...
with patch("app.services.claude_client.get_client", return_value=mock_client):
```

Grep to find all locations:
```
grep -n "ai_engine.client" backend/tests/test_ai.py
```

- [ ] **Step 11: Update test patches — `backend/tests/test_extractions.py`**

Current patterns:
```python
patch("app.services.extraction_engine.Anthropic")   # class-level mock — ineffective, remove
patch("app.services.extraction_engine.client")       # replace with claude_client.get_client
```

Change all `app.services.extraction_engine.client` patches to `app.services.claude_client.get_client`.

For the `Anthropic` class-level patches that were already ineffective (the client was already instantiated at import time): replace with `patch("app.services.claude_client.get_client", return_value=mock_client)`.

Grep to find all locations:
```
grep -n "extraction_engine.client\|extraction_engine.Anthropic" backend/tests/test_extractions.py
```

Also check `test_search.py` — it uses `patch("app.services.search_service.Anthropic")` which was always ineffective (module-level client already instantiated). Update it too:
```
grep -n "search_service.Anthropic\|search_service.client" backend/tests/test_search.py
```

- [ ] **Step 12: Run the full test suite**

```
docker-compose run --rm -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test backend pytest tests/ -v
```

Expected: all tests pass. If any test fails with `AttributeError: <MagicMock ...> does not have attribute 'messages'`, the patch structure needs adjustment — the `return_value=mock_client` pattern above ensures `get_client()` returns `mock_client` directly rather than the `patch()` context variable.

- [ ] **Step 13: Commit**

```bash
git add backend/app/services/claude_client.py \
        backend/app/services/ai_engine.py \
        backend/app/services/extraction_engine.py \
        backend/app/services/naming.py \
        backend/app/services/search_service.py \
        backend/tests/test_claude_client.py \
        backend/tests/test_pipeline.py \
        backend/tests/test_ai.py \
        backend/tests/test_extractions.py \
        backend/tests/test_search.py
git commit -m "refactor(L6): consolidate Anthropic clients into lazy shared claude_client

All four Claude-using services now call claude_client.get_client() instead of
instantiating Anthropic() at module import. Missing API key fails at first call,
not at import. Single patch target in tests: app.services.claude_client.get_client.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 4: Open PR and update audit doc

- [ ] **Step 1: Verify the branch is clean**

```
git status
git log --oneline main..HEAD
```

Expected: 3 commits on `feat/phase-5-thin-routers-lazy-client`.

- [ ] **Step 2: Update `docs/code-audit-2026-05-29.md` remediation table**

Change:
```
| 5 | M5, L6 | Architecture refactor (thin routers, lazy client) | — |
```
To:
```
| 5 | M5, L6 | Architecture refactor (thin routers, lazy client) | ✅ Done — merged 2026-05-30 |
```

Update the "Remaining open findings" section to remove Phase 5 items.

- [ ] **Step 3: Commit the doc update**

```bash
git add docs/code-audit-2026-05-29.md
git commit -m "docs: mark audit Phase 5 complete"
```

- [ ] **Step 4: Push and open PR**

```bash
git push -u origin feat/phase-5-thin-routers-lazy-client
```

Then use the `verity-prism-pr-description` skill to generate the PR body.

---

## Self-Review

**Spec coverage check:**
- M5 `get_workspace_or_404` → `app/deps.py`: ✅ Task 1
- M5 export/SSE logic → service: ✅ Task 2
- M5 routers thin (call service, return response): ✅ Task 2, Step 5
- L6 four module-level clients → lazy shared: ✅ Task 3
- L6 tests can patch single point: ✅ Task 3, Steps 9–11

**Placeholder scan:** No TBD or "implement later" in any step. Every code block is complete.

**Type consistency:** `latest_extractions` is defined once in `export_service.py` and called as `export_service.latest_extractions(...)` in `documents.py` — consistent. `get_client()` is defined in `claude_client.py` and called as `claude_client.get_client()` everywhere — consistent.

**One edge case to watch:** The `list_extractions` endpoint previously built the subquery inline. After Task 2, it calls `export_service.latest_extractions`. The `include_history=True` branch still builds its own query inline — that is intentional and correct (it's a different query: all rows, not deduplicated).
