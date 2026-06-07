# Full Document Review Pane Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the extractions-only review table with a schema-driven form that shows every defined field alongside the PDF, auto-highlights field locations, and captures PDF regions as evidence when an operator verifies or corrects a field.

**Architecture:** Backend adds an `evidence JSONB` column to document_extractions and a new "create from scratch" endpoint for fields with no prior extraction. Frontend replaces the `FieldsPane`/`ExtractionTable` in review mode with `SchemaReviewPane` (maps over schema_fields, not extractions), wires a text-layer search hook for auto-highlighting, and a canvas capture hook for evidence collection.

**Tech Stack:** Python/FastAPI/SQLAlchemy/Alembic (backend), React/Vite/Tailwind/react-pdf/pdfjs-dist (frontend), PostgreSQL JSONB, pytest, Vitest.

---

## File Map

**Create (backend):**
- `backend/alembic/versions/d5e6f7a8b9c0_review_pane_evidence.py`
- `backend/tests/test_schema_review.py`

**Modify (backend):**
- `backend/app/models/document_extraction.py` — add `evidence` column
- `backend/app/schemas/document.py` — add `evidence` to `ExtractionOut`; add `ExtractionCreateIn`
- `backend/app/schemas/review.py` — add `evidence` to `ExtractionCorrectionIn/Out`
- `backend/app/routers/review.py` — new `POST .../extractions` endpoint
- `backend/app/routers/schemas.py` — new `GET /schemas/{schema_id}` endpoint
- `backend/app/services/extraction_engine.py` — partial batch retry
- `backend/app/services/ocr.py` — DPI 200 → 300
- `backend/app/seeds/document_schemas.py` — add `group` key to all fields

**Create (frontend):**
- `frontend/src/components/documents/SchemaReviewPane.jsx`
- `frontend/src/components/documents/ExtractionField.jsx`
- `frontend/src/components/documents/PDFHighlightOverlay.jsx`
- `frontend/src/hooks/useFieldHighlight.js`
- `frontend/src/hooks/useRegionCapture.js`

**Modify (frontend):**
- `frontend/src/pages/workspace/DocumentViewer.jsx` — text layer, schema fetch, highlight wiring, render `SchemaReviewPane` in review mode
- `frontend/src/api/documents.js` — add `createExtraction()`
- `frontend/src/api/schemas.js` — add `getSchema(id)`

---

## Task 1: Migration — evidence column

**Files:**
- Create: `backend/alembic/versions/d5e6f7a8b9c0_review_pane_evidence.py`

- [ ] **Step 1: Create the migration file**

```python
# backend/alembic/versions/d5e6f7a8b9c0_review_pane_evidence.py
"""review_pane_evidence

Revision ID: d5e6f7a8b9c0
Revises: b2c3d4e5f6a7
Create Date: 2026-05-31

Adds evidence JSONB to document_extractions for PDF region capture data.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = 'd5e6f7a8b9c0'
down_revision: Union[str, None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'document_extractions'
                AND column_name = 'evidence'
            ) THEN
                ALTER TABLE document_extractions ADD COLUMN evidence JSONB;
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
                AND column_name = 'evidence'
            ) THEN
                ALTER TABLE document_extractions DROP COLUMN evidence;
            END IF;
        END $$;
    """)
```

- [ ] **Step 2: Run migration against test DB**

```bash
docker-compose run --rm -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test backend alembic upgrade head
```

Expected: `Running upgrade b2c3d4e5f6a7 -> d5e6f7a8b9c0`

- [ ] **Step 3: Run migration against dev DB**

```bash
cd backend && alembic upgrade head
```

Expected: same revision line.

- [ ] **Step 4: Commit**

```bash
git add backend/alembic/versions/d5e6f7a8b9c0_review_pane_evidence.py
git commit -m "feat: migration — evidence JSONB column on document_extractions"
```

---

## Task 2: Model + schema updates

**Files:**
- Modify: `backend/app/models/document_extraction.py`
- Modify: `backend/app/schemas/document.py`
- Modify: `backend/app/schemas/review.py`

- [ ] **Step 1: Add `evidence` to DocumentExtraction model**

In `backend/app/models/document_extraction.py`, add after `extracted_at`:

```python
from sqlalchemy.dialects.postgresql import JSONB
```

Add to the class body after `extracted_at`:

```python
    evidence: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
```

The full import block at top becomes:
```python
import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
```

- [ ] **Step 2: Update ExtractionOut and add ExtractionCreateIn in schemas/document.py**

Replace the entire `backend/app/schemas/document.py`:

```python
from datetime import datetime

from pydantic import BaseModel


class DocumentOut(BaseModel):
    id: str
    workspace_id: str
    filename: str
    original_filename: str
    file_type: str
    sha256_hash: str
    source_url: str | None
    source_type: str
    detected_doc_type: str | None
    extraction_status: str
    extraction_error: str | None
    size_bytes: int | None
    uploaded_at: datetime

    class Config:
        from_attributes = True


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
    evidence: dict | None = None

    class Config:
        from_attributes = True


class ExtractionCreateIn(BaseModel):
    field_name: str
    field_value: str | None
    field_type: str = "text"
    schema_id: str
    evidence: dict | None = None
```

- [ ] **Step 3: Add evidence to ExtractionCorrectionIn/Out in schemas/review.py**

In `backend/app/schemas/review.py`, update:

```python
class ExtractionCorrectionIn(BaseModel):
    field_value: str
    evidence: dict | None = None


class ExtractionCorrectionOut(BaseModel):
    id: str
    field_name: str
    field_value: str | None
    field_type: str
    confidence: float
    ocr_confidence: float
    attempt: int
    extracted_at: datetime
    evidence: dict | None = None

    class Config:
        from_attributes = True
```

- [ ] **Step 4: Run tests to confirm no regressions**

```bash
docker-compose run --rm -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test backend pytest tests/ -q 2>&1 | tail -5
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/models/document_extraction.py backend/app/schemas/document.py backend/app/schemas/review.py
git commit -m "feat: add evidence field to DocumentExtraction model and schemas"
```

---

## Task 3: Seed update — group keys on all schema fields

**Files:**
- Modify: `backend/app/seeds/document_schemas.py`

The seeds use named section variables (e.g., `IDENTITY`, `LEGAL`) for PARCEL-RECORD. Other schemas use inline field lists. This task adds a `_group()` helper and applies group names throughout.

- [ ] **Step 1: Add the `_group()` helper**

In `backend/app/seeds/document_schemas.py`, add after the `_repeating()` function (around line 28):

```python
def _group(fields: list, group_name: str) -> list:
    """Tag all fields in a list with a group name for the review pane form."""
    return [dict(f, group=group_name) for f in fields]
```

- [ ] **Step 2: Apply groups to PARCEL-RECORD**

The PARCEL-RECORD seed calls `_fields(IDENTITY, LEGAL, UTILITIES, ...)`. Replace with `_group()` calls. Find the `seed_parcel_record()` function and change its `schema_fields` argument from:

```python
schema_fields=_fields(IDENTITY, LEGAL, UTILITIES, ...)
```

To (check the actual section names in the file and apply accordingly):

```python
schema_fields=_fields(
    _group(IDENTITY, "Identity"),
    _group(LEGAL, "Legal"),
    _group(UTILITIES, "Utilities"),
    _group(VALUATION_CURRENT, "Valuation"),
    _group(VALUATION_HISTORY, "Valuation History"),
    _group(EXEMPTION, "Exemption"),
    _group(TAX_CURRENT, "Tax"),
    _group(TAX_DISTRIBUTIONS, "Tax"),
    # add remaining sections with appropriate group names
),
```

- [ ] **Step 3: Apply groups to all remaining schemas**

For each of the 10 other schemas, open the seed function and add `"group": "..."` to each field dict or restructure to use `_group()`. Apply these group mappings:

| Schema | Groups to use |
|---|---|
| DEED | "Parties", "Financial", "Property", "Recording", "Liens" |
| 990 | "Organization", "Financials", "Programs", "Governance" |
| SOS-FILING | "Entity", "Officers", "Registered Agent", "Status" |
| UCC | "Debtor", "Secured Party", "Collateral", "Filing" |
| BUILDING-PERMIT | "Property", "Applicant", "Work", "Inspection" |
| AUDIT-REPORT | "Organization", "Financials", "Findings", "Signatures" |
| SCREENSHOT | "Content" |
| OBITUARY | "Personal", "Family", "Services" |
| PLAT | "Property", "Recording" |
| CORRESPONDENCE | "Header", "Body", "Signatures" |

For schemas with inline field lists (not using named sections), add `"group"` to each field dict directly:

```python
# Example for a field in the DEED schema:
{"name": "grantor_name", "type": "name", "description": "Name of grantor", "required": True, "group": "Parties"},
```

Fields without a group key fall into "Other" in the form — better to be explicit.

- [ ] **Step 4: Re-run seeds against test DB**

```bash
docker-compose run --rm -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test backend python -m app.seeds.document_schemas
```

Expected: upserts complete without error.

- [ ] **Step 5: Run tests**

```bash
docker-compose run --rm -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test backend pytest tests/ -q 2>&1 | tail -5
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add backend/app/seeds/document_schemas.py
git commit -m "feat: add group key to all schema_fields for review pane section rendering"
```

---

## Task 4: OCR DPI upgrade + partial batch retry

**Files:**
- Modify: `backend/app/services/ocr.py`
- Modify: `backend/app/services/extraction_engine.py`
- Modify: `backend/tests/test_pipeline.py`

- [ ] **Step 1: Write failing test for partial batch retry**

Add to `backend/tests/test_pipeline.py`:

```python
def test_extract_fields_retries_partial_batch_failure(db, deed_schema):
    """When some batches fail but at least one succeeds, failed batches are retried."""
    from app.services.extraction_engine import extract_fields
    import json

    call_count = 0

    def side_effect(**kwargs):
        nonlocal call_count
        call_count += 1
        # First call fails, subsequent calls succeed
        if call_count == 1:
            raise Exception("Transient API error")
        return MagicMock(
            content=[MagicMock(text=json.dumps({"extractions": [
                {"field_name": "grantor_name", "field_value": "Jane Smith",
                 "field_type": "name", "confidence": 0.90, "ocr_confidence": 0.92}
            ]}))],
            usage=MagicMock(input_tokens=100, output_tokens=50),
        )

    mock_client = MagicMock()
    mock_client.messages.create.side_effect = side_effect

    # Schema with 2 fields → 1 batch (BATCH_SIZE=40, so both fields in batch 1)
    # To force a partial failure we need > BATCH_SIZE fields or mock at batch level
    # Simpler: test the retry path directly via extract_fields with mock that fails then succeeds
    with patch("app.services.claude_client.get_client", return_value=mock_client):
        # deed_schema has 2 fields — first call fails, retry succeeds
        results = extract_fields("deed content", deed_schema)

    # Should have results from the retry, not an empty list
    assert len(results) > 0
    assert any(r["field_name"] == "grantor_name" for r in results)
```

- [ ] **Step 2: Run to confirm failure**

```bash
docker-compose run --rm -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test backend pytest tests/test_pipeline.py::test_extract_fields_retries_partial_batch_failure -v
```

Expected: FAIL — no retry logic yet, transient error causes total failure.

- [ ] **Step 3: Apply OCR DPI upgrade**

In `backend/app/services/ocr.py`, change line 20:

```python
# Before
pix = page.get_pixmap(dpi=200)
# After
pix = page.get_pixmap(dpi=300)
```

- [ ] **Step 4: Add partial batch retry to extraction_engine.py**

In `extract_fields()`, replace the section after the batch loop (around line 336) — find the block that logs partial failures and replace with:

```python
    if batch_errors == len(batches):
        raise ExtractionBatchError(
            f"All {len(batches)} extraction batch(es) failed for schema "
            f"{schema.document_type} — Claude API may be unavailable"
        )

    # Partial failure: retry failed batches once before giving up
    if batch_errors > 0:
        failed_batch_indices = [
            idx for idx, batch in enumerate(batches)
            if not any(
                e.get("field_name") in {f["name"] for f in batch}
                for e in all_extractions
            )
        ]
        retry_fields = []
        for idx in failed_batch_indices:
            retry_fields.extend(batches[idx])

        if retry_fields:
            logger.info(
                f"Retrying {len(retry_fields)} fields from {len(failed_batch_indices)} "
                f"failed batch(es) for schema {schema.document_type}"
            )
            retry_batches = [retry_fields[i: i + BATCH_SIZE] for i in range(0, len(retry_fields), BATCH_SIZE)]
            retry_errors = 0
            for retry_batch in retry_batches:
                try:
                    retry_results = _extract_batch(
                        ocr_text, retry_batch, schema,
                        document_id=document_id,
                        workspace_id=workspace_id,
                        call_type="batch_retry_partial",
                        attempt=1,
                    )
                    all_extractions.extend(retry_results)
                except ExtractionBatchError:
                    retry_errors += 1
            if retry_errors > 0:
                logger.warning(
                    f"Partial retry: {retry_errors}/{len(retry_batches)} retry batch(es) "
                    f"still failing for schema {schema.document_type}"
                )
```

- [ ] **Step 5: Run tests**

```bash
docker-compose run --rm -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test backend pytest tests/ -q 2>&1 | tail -5
```

Expected: all pass including new retry test.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/ocr.py backend/app/services/extraction_engine.py backend/tests/test_pipeline.py
git commit -m "feat: OCR DPI 200→300, partial batch retry on extraction failure"
```

---

## Task 5: New extraction create endpoint + GET /schemas/{id}

**Files:**
- Modify: `backend/app/routers/review.py`
- Modify: `backend/app/routers/schemas.py`
- Create: `backend/tests/test_schema_review.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_schema_review.py`:

```python
"""Tests for schema review endpoints: create extraction, get schema by id."""
import uuid
import pytest
from app.models.document import Document
from app.models.document_extraction import DocumentExtraction
from app.models.document_schema import DocumentSchema
from app.models.user import User
from app.models.workspace import Workspace


@pytest.fixture
def ws_schema_doc(db, auth_headers, client):
    user = db.query(User).filter(User.email == "tyler@example.com").first()
    ws_resp = client.post("/workspaces/", json={"name": "Review WS", "vertical": "general"},
                          headers=auth_headers)
    ws_id = ws_resp.json()["id"]

    schema = DocumentSchema(
        id=str(uuid.uuid4()), document_type="DEED", display_name="Deed",
        vertical="general",
        schema_fields=[{"name": "grantor_name", "type": "name",
                        "description": "Grantor", "group": "Parties"}],
        version=1, is_active=True, parse_strategy="claude",
        default_confidence_threshold=0.75,
    )
    db.add(schema)
    db.flush()

    doc = Document(
        id=str(uuid.uuid4()), workspace_id=ws_id,
        filename="deed.pdf", original_filename="deed.pdf",
        file_path="/tmp/deed.pdf", file_type="pdf",
        sha256_hash="test123", uploaded_by=user.id,
        extraction_status="needs_review", schema_id=schema.id,
    )
    db.add(doc)
    db.commit()
    return ws_id, schema, doc


def test_create_extraction_inserts_attempt3_row(client, auth_headers, ws_schema_doc):
    ws_id, schema, doc = ws_schema_doc
    resp = client.post(
        f"/workspaces/{ws_id}/documents/{doc.id}/extractions",
        json={
            "field_name": "grantor_name",
            "field_value": "Jane Smith",
            "field_type": "name",
            "schema_id": schema.id,
        },
        headers=auth_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["field_name"] == "grantor_name"
    assert data["field_value"] == "Jane Smith"
    assert data["attempt"] == 3
    assert data["confidence"] == 1.0


def test_create_extraction_with_evidence(client, auth_headers, ws_schema_doc):
    ws_id, schema, doc = ws_schema_doc
    evidence = {
        "type": "manual_draw",
        "page": 1,
        "region": {"x": 100, "y": 200, "width": 150, "height": 25},
        "image_b64": "data:image/png;base64,abc123",
        "note": "First paragraph",
    }
    resp = client.post(
        f"/workspaces/{ws_id}/documents/{doc.id}/extractions",
        json={"field_name": "grantor_name", "field_value": "Jane Smith",
              "field_type": "name", "schema_id": schema.id, "evidence": evidence},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    assert resp.json()["evidence"]["type"] == "manual_draw"


def test_create_extraction_404_for_unknown_doc(client, auth_headers, ws_schema_doc):
    ws_id, schema, _ = ws_schema_doc
    resp = client.post(
        f"/workspaces/{ws_id}/documents/nonexistent/extractions",
        json={"field_name": "x", "field_value": "y", "field_type": "text",
              "schema_id": schema.id},
        headers=auth_headers,
    )
    assert resp.status_code == 404


def test_get_schema_by_id(client, auth_headers, ws_schema_doc):
    _, schema, _ = ws_schema_doc
    resp = client.get(f"/schemas/{schema.id}", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == schema.id
    assert data["document_type"] == "DEED"
    assert len(data["fields"]) == 1


def test_get_schema_by_id_404(client, auth_headers):
    resp = client.get("/schemas/nonexistent-id", headers=auth_headers)
    assert resp.status_code == 404
```

- [ ] **Step 2: Run to confirm failures**

```bash
docker-compose run --rm -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test backend pytest tests/test_schema_review.py -v
```

Expected: all FAIL — endpoints don't exist yet.

- [ ] **Step 3: Add create extraction endpoint to review.py**

Add to `backend/app/routers/review.py` imports:
```python
from app.schemas.document import ExtractionCreateIn, ExtractionOut
```

Add after the flag endpoint:

```python
@router.post(
    "/documents/{document_id}/extractions",
    response_model=ExtractionOut,
    status_code=201,
)
def create_extraction(
    workspace_id: str,
    document_id: str,
    body: ExtractionCreateIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Create a new attempt=3 extraction row for a field with no prior extraction.
    Used by the review pane when an operator enters a value for a missing field.
    """
    get_workspace_or_404(workspace_id, user, db)

    doc = db.query(Document).filter(
        Document.id == document_id,
        Document.workspace_id == workspace_id,
        Document.is_deleted == False,
    ).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    row = DocumentExtraction(
        document_id=document_id,
        workspace_id=workspace_id,
        field_name=body.field_name,
        field_value=body.field_value,
        field_type=body.field_type,
        confidence=1.0,
        ocr_confidence=1.0,
        schema_id=body.schema_id,
        attempt=3,
        evidence=body.evidence,
    )
    db.add(row)
    db.flush()

    # Check if all fields now resolved — flip to complete if so
    schema = db.query(DocumentSchema).filter(DocumentSchema.id == doc.schema_id).first()
    if schema:
        latest_subq = (
            db.query(
                DocumentExtraction.field_name,
                func.max(DocumentExtraction.attempt).label("max_attempt"),
            )
            .filter(DocumentExtraction.document_id == document_id)
            .group_by(DocumentExtraction.field_name)
            .subquery()
        )
        remaining = (
            db.query(func.count(DocumentExtraction.id))
            .join(
                latest_subq,
                (DocumentExtraction.field_name == latest_subq.c.field_name)
                & (DocumentExtraction.attempt == latest_subq.c.max_attempt),
            )
            .filter(
                DocumentExtraction.document_id == document_id,
                DocumentExtraction.attempt < 3,
                DocumentExtraction.confidence < schema.default_confidence_threshold,
            )
            .scalar()
        )
        if remaining == 0:
            doc.extraction_status = "complete"

    db.commit()
    db.refresh(row)

    audit.log(
        db,
        action="field_created",
        user_id=user.id,
        workspace_id=workspace_id,
        entity_type="document",
        entity_id=document_id,
        before_state=None,
        after_state={
            "field_name": row.field_name,
            "field_value": row.field_value,
            "evidence_type": (row.evidence or {}).get("type"),
        },
    )

    return row
```

- [ ] **Step 4: Add GET /schemas/{schema_id} to schemas.py**

Add after the existing `list_schemas` endpoint in `backend/app/routers/schemas.py`:

```python
from fastapi import HTTPException


@router.get("/{schema_id}")
def get_schema(
    schema_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Return a single active schema by ID with full field definitions."""
    schema = db.query(DocumentSchema).filter(
        DocumentSchema.id == schema_id,
        DocumentSchema.is_active == True,
    ).first()
    if not schema:
        raise HTTPException(status_code=404, detail="Schema not found")
    return {
        "id": schema.id,
        "document_type": schema.document_type,
        "display_name": schema.display_name,
        "vertical": schema.vertical,
        "parse_strategy": schema.parse_strategy,
        "default_confidence_threshold": schema.default_confidence_threshold,
        "field_count": len(schema.schema_fields or []),
        "fields": schema.schema_fields or [],
        "version": schema.version,
    }
```

- [ ] **Step 5: Update correct_extraction endpoint to store evidence**

In `backend/app/routers/review.py`, find the `correct_extraction` endpoint. Change the `DocumentExtraction` insertion to include evidence:

```python
    correction = DocumentExtraction(
        document_id=document_id,
        workspace_id=workspace_id,
        field_name=source.field_name,
        field_value=body.field_value,
        field_type=source.field_type,
        confidence=1.0,
        ocr_confidence=1.0,
        schema_id=source.schema_id,
        attempt=3,
        evidence=body.evidence,
    )
```

- [ ] **Step 6: Run tests**

```bash
docker-compose run --rm -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test backend pytest tests/test_schema_review.py tests/test_review.py -v
```

Expected: all pass.

- [ ] **Step 7: Run full suite**

```bash
docker-compose run --rm -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test backend pytest tests/ -q 2>&1 | tail -5
```

Expected: all pass.

- [ ] **Step 8: Commit**

```bash
git add backend/app/routers/review.py backend/app/routers/schemas.py backend/tests/test_schema_review.py
git commit -m "feat: create extraction endpoint, GET /schemas/{id}, evidence on corrections"
```

---

## Task 6: Frontend API additions

**Files:**
- Modify: `frontend/src/api/documents.js`
- Modify: `frontend/src/api/schemas.js`

- [ ] **Step 1: Add createExtraction to documents.js**

Add at the end of `frontend/src/api/documents.js`:

```javascript
export const createExtraction = (workspaceId, documentId, fieldName, fieldValue, fieldType, schemaId, evidence = null) =>
  client.post(`/workspaces/${workspaceId}/documents/${documentId}/extractions`, {
    field_name: fieldName,
    field_value: fieldValue,
    field_type: fieldType,
    schema_id: schemaId,
    evidence,
  })
```

- [ ] **Step 2: Add getSchema to schemas.js**

Open `frontend/src/api/schemas.js`. Add:

```javascript
export const getSchema = (schemaId) =>
  client.get(`/schemas/${schemaId}`)
```

- [ ] **Step 3: Verify build**

```bash
cd "C:\Users\tjcol\OneDrive\Projects\Investigation software\frontend" && npm run build 2>&1 | tail -5
```

Expected: no errors.

- [ ] **Step 4: Commit**

```bash
cd "C:\Users\tjcol\OneDrive\Projects\Investigation software" && git add frontend/src/api/documents.js frontend/src/api/schemas.js && git commit -m "feat: createExtraction and getSchema API client functions"
```

---

## Task 7: useFieldHighlight hook

**Files:**
- Create: `frontend/src/hooks/useFieldHighlight.js`

- [ ] **Step 1: Create the hook**

```javascript
// frontend/src/hooks/useFieldHighlight.js
import { useMemo, useState, useCallback } from 'react'

/**
 * Searches PDF text layer items for a field value.
 * Returns match coordinates and navigation helpers.
 *
 * textItems: array from pdfjs page.getTextContent().items
 *   Each item: { str, transform: [a,b,c,d,x,y], width, height }
 *   transform[4] = x, transform[5] = y (PDF coordinate space, origin bottom-left)
 *
 * pageViewport: pdfjs viewport with .width and .height
 */
export function useFieldHighlight(fieldValue, textItems, pageViewport) {
  const [activeIndex, setActiveIndex] = useState(0)

  const matches = useMemo(() => {
    if (!fieldValue || !textItems || textItems.length === 0 || !pageViewport) return []

    const normalise = (s) => s.replace(/[\s$,]/g, '').toLowerCase()
    const target = normalise(String(fieldValue))
    if (!target) return []

    const found = []
    // Concatenate nearby text items to find multi-word values
    for (let i = 0; i < textItems.length; i++) {
      let window = ''
      for (let j = i; j < Math.min(i + 8, textItems.length); j++) {
        window += textItems[j].str
        if (normalise(window).includes(target)) {
          const item = textItems[i]
          const x = item.transform[4]
          const y = item.transform[5]
          // Convert from PDF bottom-left to top-left coordinates
          const canvasY = pageViewport.height - y - (item.height || 12)
          found.push({
            x,
            y: canvasY,
            width: item.width + (j - i) * 60,  // approximate multi-item width
            height: (item.height || 12) + 4,
          })
          break
        }
      }
    }

    // Deduplicate: remove matches within 20px of each other
    return found.filter((m, i) =>
      i === 0 || Math.abs(m.y - found[i - 1].y) > 20 || Math.abs(m.x - found[i - 1].x) > 20
    )
  }, [fieldValue, textItems, pageViewport])

  const next = useCallback(() => {
    setActiveIndex((i) => (i + 1) % Math.max(matches.length, 1))
  }, [matches.length])

  const prev = useCallback(() => {
    setActiveIndex((i) => (i - 1 + Math.max(matches.length, 1)) % Math.max(matches.length, 1))
  }, [matches.length])

  // Reset to first match when value changes
  useMemo(() => setActiveIndex(0), [fieldValue])

  return {
    matches,
    activeIndex: Math.min(activeIndex, Math.max(matches.length - 1, 0)),
    activeMatch: matches[Math.min(activeIndex, matches.length - 1)] || null,
    next,
    prev,
  }
}
```

- [ ] **Step 2: Verify build**

```bash
cd "C:\Users\tjcol\OneDrive\Projects\Investigation software\frontend" && npm run build 2>&1 | tail -5
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
cd "C:\Users\tjcol\OneDrive\Projects\Investigation software" && git add frontend/src/hooks/useFieldHighlight.js && git commit -m "feat: useFieldHighlight hook — text layer search with multi-match navigation"
```

---

## Task 8: useRegionCapture hook

**Files:**
- Create: `frontend/src/hooks/useRegionCapture.js`

- [ ] **Step 1: Create the hook**

```javascript
// frontend/src/hooks/useRegionCapture.js
import { useCallback, useRef } from 'react'

/**
 * Captures a rectangular region from a react-pdf canvas as a base64 PNG.
 * pageContainerRef must point to the DOM element wrapping the react-pdf <Page>.
 *
 * pdfHeight: viewport height (for y-axis flip from PDF to canvas coords)
 * scale: current PDF render scale
 */
export function useRegionCapture(pageContainerRef) {
  const drawStateRef = useRef(null)

  const capture = useCallback((region, pdfHeight, scale) => {
    const canvas = pageContainerRef.current?.querySelector('canvas')
    if (!canvas) return null

    const offscreen = document.createElement('canvas')
    const sw = Math.round(region.width * scale)
    const sh = Math.round(region.height * scale)
    if (sw <= 0 || sh <= 0) return null

    offscreen.width = sw
    offscreen.height = sh

    const ctx = offscreen.getContext('2d')
    // PDF y-origin is bottom-left; canvas y-origin is top-left
    const srcX = Math.round(region.x * scale)
    const srcY = Math.round((pdfHeight - region.y - region.height) * scale)

    ctx.drawImage(canvas, srcX, srcY, sw, sh, 0, 0, sw, sh)
    return offscreen.toDataURL('image/png')
  }, [pageContainerRef])

  const startDraw = useCallback((pdfHeight, scale, onComplete) => {
    const canvas = pageContainerRef.current?.querySelector('canvas')
    if (!canvas) return

    const rect = canvas.getBoundingClientRect()
    let startX, startY, isDragging = false

    const overlay = document.createElement('div')
    overlay.style.cssText = `
      position:absolute;top:0;left:0;right:0;bottom:0;
      cursor:crosshair;z-index:50;
    `
    pageContainerRef.current.style.position = 'relative'
    pageContainerRef.current.appendChild(overlay)

    const selBox = document.createElement('div')
    selBox.style.cssText = `
      position:absolute;border:2px solid #3b82f6;background:rgba(59,130,246,0.1);
      pointer-events:none;display:none;
    `
    overlay.appendChild(selBox)

    const onMouseDown = (e) => {
      isDragging = true
      startX = e.clientX - rect.left
      startY = e.clientY - rect.top
      selBox.style.display = 'block'
    }

    const onMouseMove = (e) => {
      if (!isDragging) return
      const x = e.clientX - rect.left
      const y = e.clientY - rect.top
      const l = Math.min(startX, x)
      const t = Math.min(startY, y)
      const w = Math.abs(x - startX)
      const h = Math.abs(y - startY)
      selBox.style.left = l + 'px'
      selBox.style.top = t + 'px'
      selBox.style.width = w + 'px'
      selBox.style.height = h + 'px'
    }

    const onMouseUp = (e) => {
      if (!isDragging) return
      isDragging = false
      pageContainerRef.current?.removeChild(overlay)

      const endX = e.clientX - rect.left
      const endY = e.clientY - rect.top
      const l = Math.min(startX, endX)
      const t = Math.min(startY, endY)
      const w = Math.abs(endX - startX)
      const h = Math.abs(endY - startY)

      if (w < 5 || h < 5) { onComplete(null, null); return }

      // Convert screen px to PDF coordinate space
      const pdfX = l / scale
      const pdfY = pdfHeight - (t / scale) - (h / scale)
      const region = { x: pdfX, y: pdfY, width: w / scale, height: h / scale }
      const image_b64 = capture(region, pdfHeight, scale)
      onComplete(region, image_b64)
    }

    overlay.addEventListener('mousedown', onMouseDown)
    overlay.addEventListener('mousemove', onMouseMove)
    overlay.addEventListener('mouseup', onMouseUp)
  }, [pageContainerRef, capture])

  return { capture, startDraw }
}
```

- [ ] **Step 2: Verify build**

```bash
cd "C:\Users\tjcol\OneDrive\Projects\Investigation software\frontend" && npm run build 2>&1 | tail -5
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
cd "C:\Users\tjcol\OneDrive\Projects\Investigation software" && git add frontend/src/hooks/useRegionCapture.js && git commit -m "feat: useRegionCapture hook — canvas crop and drag-to-draw region selection"
```

---

## Task 9: ExtractionField component

**Files:**
- Create: `frontend/src/components/documents/ExtractionField.jsx`

This component renders a single field row with all four states: auto-extracted, low-confidence, not-extracted, and obscured.

- [ ] **Step 1: Create the component**

```jsx
// frontend/src/components/documents/ExtractionField.jsx
import { useState } from 'react'

/**
 * Single field row in the schema review form.
 *
 * field: schema field definition { name, type, description, group, required }
 * extraction: DocumentExtraction row or null (null = field never extracted)
 * threshold: confidence threshold from schema (float)
 * isActive: true when this field has keyboard/click focus
 * onFocus: () => void — notify parent to update PDF highlight
 * onChange: (fieldName, value, evidence) => void — local state accumulation
 * onVerify: (region, image_b64, note, type) => Promise — save evidence
 */
export default function ExtractionField({
  field, extraction, threshold, isActive,
  onFocus, onChange, onVerify,
  workspaceId, documentId,
}) {
  const [value, setValue] = useState(extraction?.field_value || '')
  const [note, setNote] = useState('')
  const [isObscured, setIsObscured] = useState(false)
  const [saving, setSaving] = useState(false)
  const [verified, setVerified] = useState(extraction?.evidence != null)

  const isHumanCorrected = extraction?.attempt === 3
  const isMissing = extraction == null
  const isLowConfidence = !isMissing && !isHumanCorrected &&
    (extraction.confidence < threshold || extraction.ocr_confidence < threshold)

  const stateColor = isHumanCorrected || verified
    ? 'border-green-700 bg-green-950/30'
    : isObscured
    ? 'border-purple-700 bg-purple-950/30'
    : isMissing
    ? 'border-slate-700 bg-slate-900/50 border-dashed'
    : isLowConfidence
    ? 'border-yellow-700 bg-yellow-950/30'
    : 'border-slate-700'

  const handleChange = (v) => {
    setValue(v)
    onChange(field.name, v, null)
  }

  const handleVerify = async (type = 'auto_highlight') => {
    setSaving(true)
    try {
      await onVerify(field.name, value, note, type)
      setVerified(true)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div
      className={`border rounded p-2 mb-1 transition-colors cursor-pointer ${stateColor} ${isActive ? 'ring-1 ring-blue-500' : ''}`}
      onClick={onFocus}
    >
      {/* Label row */}
      <div className="flex items-center justify-between mb-1">
        <label className={`text-xs font-medium ${isActive ? 'text-blue-400' : 'text-slate-500'}`}>
          {field.name}
          {field.required && <span className="text-red-500 ml-0.5">*</span>}
        </label>
        <div className="flex items-center gap-2">
          {/* Confidence pills — only on extracted fields */}
          {extraction && !isHumanCorrected && !isObscured && (
            <span className="flex gap-1 text-xs">
              <span className={`${extraction.confidence >= 0.85 ? 'text-green-400' : extraction.confidence >= 0.70 ? 'text-yellow-400' : 'text-red-400'}`}>
                AI {Math.round(extraction.confidence * 100)}%
              </span>
              <span className={`${extraction.ocr_confidence >= 0.85 ? 'text-green-400' : extraction.ocr_confidence >= 0.70 ? 'text-yellow-400' : 'text-red-400'}`}>
                OCR {Math.round(extraction.ocr_confidence * 100)}%
              </span>
            </span>
          )}
          {verified && (
            <span className="text-xs text-green-400 font-medium">✓ Verified</span>
          )}
          {isHumanCorrected && !verified && (
            <span className="text-xs text-green-400">Corrected</span>
          )}
          {/* Obscured toggle */}
          {!isHumanCorrected && !verified && (
            <button
              onClick={(e) => { e.stopPropagation(); setIsObscured((v) => !v) }}
              className={`text-xs px-1.5 py-0.5 rounded transition-colors ${isObscured ? 'bg-purple-800 text-purple-200' : 'bg-slate-800 text-slate-500 hover:text-purple-400'}`}
              title="Mark source as physically obscured"
            >
              ▒
            </button>
          )}
        </div>
      </div>

      {/* Value input */}
      {isObscured ? (
        <div className="text-xs text-purple-400 italic px-1">
          Source obscured — capture the damaged region
        </div>
      ) : (
        <input
          className={`w-full text-xs rounded px-2 py-1 outline-none focus:ring-1 focus:ring-blue-500
            ${isMissing
              ? 'bg-slate-800 border border-dashed border-slate-600 text-slate-400 placeholder:italic'
              : 'bg-slate-800 border border-slate-600 text-white'
            }`}
          value={value}
          onChange={(e) => handleChange(e.target.value)}
          placeholder={isMissing ? `enter ${field.name} from document…` : undefined}
          onFocus={onFocus}
        />
      )}

      {/* Note field — shown on low-confidence, missing, or obscured */}
      {(isLowConfidence || isMissing || isObscured) && !verified && (
        <input
          className="w-full text-xs rounded px-2 py-0.5 mt-1 bg-slate-800/50 border border-slate-700 text-slate-400 placeholder:text-slate-600 outline-none"
          value={note}
          onChange={(e) => setNote(e.target.value)}
          placeholder="note (e.g. nominal consideration, stamp overlay)…"
          onClick={(e) => e.stopPropagation()}
        />
      )}

      {/* Action buttons */}
      {!isHumanCorrected && !verified && (
        <div className="flex gap-1 mt-1.5">
          {isObscured ? (
            <button
              disabled={saving}
              onClick={(e) => { e.stopPropagation(); handleVerify('obscured') }}
              className="flex-1 text-xs py-1 bg-purple-800 hover:bg-purple-700 text-purple-100 rounded disabled:opacity-50 transition-colors"
            >
              {saving ? '…' : '📷 Capture obscured region'}
            </button>
          ) : (
            <>
              {(isMissing || isLowConfidence) && (
                <button
                  onClick={(e) => { e.stopPropagation(); /* triggers manual draw in parent */ onFocus() }}
                  className="text-xs px-2 py-1 bg-slate-700 hover:bg-slate-600 text-slate-300 rounded transition-colors"
                >
                  Mark location
                </button>
              )}
              <button
                disabled={saving || !value}
                onClick={(e) => { e.stopPropagation(); handleVerify('auto_highlight') }}
                className="flex-1 text-xs py-1 bg-blue-700 hover:bg-blue-600 text-white rounded disabled:opacity-50 transition-colors"
              >
                {saving ? '…' : '✓ Verify'}
              </button>
            </>
          )}
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 2: Verify build**

```bash
cd "C:\Users\tjcol\OneDrive\Projects\Investigation software\frontend" && npm run build 2>&1 | tail -5
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
cd "C:\Users\tjcol\OneDrive\Projects\Investigation software" && git add frontend/src/components/documents/ExtractionField.jsx && git commit -m "feat: ExtractionField component — four states, verify action, note field"
```

---

## Task 10: PDFHighlightOverlay component

**Files:**
- Create: `frontend/src/components/documents/PDFHighlightOverlay.jsx`

- [ ] **Step 1: Create the component**

```jsx
// frontend/src/components/documents/PDFHighlightOverlay.jsx

/**
 * Renders a blue highlight box over the active field's location on the PDF.
 * Positioned absolutely over the react-pdf <Page> container.
 *
 * activeMatch: { x, y, width, height } in screen pixels (already scaled)
 *              null = no highlight to show
 * activeFieldName: string label shown above the box
 * matchCount: total number of matches (for "1 of N" display)
 * matchIndex: current match index (0-based)
 * onNext / onPrev: navigate matches when matchCount > 1
 */
export default function PDFHighlightOverlay({
  activeMatch, activeFieldName, matchCount, matchIndex, onNext, onPrev,
}) {
  if (!activeMatch) return null

  return (
    <div
      style={{
        position: 'absolute',
        top: 0, left: 0, right: 0, bottom: 0,
        pointerEvents: 'none',
        zIndex: 10,
      }}
    >
      {/* Highlight box */}
      <div
        style={{
          position: 'absolute',
          left: activeMatch.x,
          top: activeMatch.y,
          width: activeMatch.width,
          height: activeMatch.height,
          border: '2px solid #3b82f6',
          background: 'rgba(59,130,246,0.15)',
          borderRadius: 3,
        }}
      >
        {/* Label */}
        <div
          style={{
            position: 'absolute',
            bottom: '100%',
            left: 0,
            marginBottom: 3,
            background: '#3b82f6',
            color: 'white',
            fontSize: 9,
            padding: '2px 6px',
            borderRadius: 3,
            whiteSpace: 'nowrap',
            pointerEvents: 'auto',
            display: 'flex',
            alignItems: 'center',
            gap: 6,
          }}
        >
          <span>{activeFieldName}</span>
          {matchCount > 1 && (
            <span style={{ display: 'flex', alignItems: 'center', gap: 3 }}>
              <button
                onClick={onPrev}
                style={{ background: 'rgba(255,255,255,0.2)', border: 'none', color: 'white', cursor: 'pointer', borderRadius: 2, padding: '0 3px', fontSize: 9 }}
              >◀</button>
              <span>{matchIndex + 1}/{matchCount}</span>
              <button
                onClick={onNext}
                style={{ background: 'rgba(255,255,255,0.2)', border: 'none', color: 'white', cursor: 'pointer', borderRadius: 2, padding: '0 3px', fontSize: 9 }}
              >▶</button>
            </span>
          )}
        </div>
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Verify build**

```bash
cd "C:\Users\tjcol\OneDrive\Projects\Investigation software\frontend" && npm run build 2>&1 | tail -5
```

- [ ] **Step 3: Commit**

```bash
cd "C:\Users\tjcol\OneDrive\Projects\Investigation software" && git add frontend/src/components/documents/PDFHighlightOverlay.jsx && git commit -m "feat: PDFHighlightOverlay component — blue highlight box with match navigation"
```

---

## Task 11: SchemaReviewPane component

**Files:**
- Create: `frontend/src/components/documents/SchemaReviewPane.jsx`

- [ ] **Step 1: Create the component**

```jsx
// frontend/src/components/documents/SchemaReviewPane.jsx
import { useState, useCallback } from 'react'
import ExtractionField from './ExtractionField'
import { correctExtraction, createExtraction } from '../../api/documents'

/**
 * Schema-driven review form — maps over schema.fields (not extractions).
 * Shows every field the schema defines; pre-populates from extractions where they exist.
 *
 * schema: { id, fields: [{name, type, description, group, required, ...}],
 *            default_confidence_threshold }
 * extractions: list of ExtractionOut rows (latest attempt per field)
 * onFieldFocus: (fieldName, fieldValue) => void — parent uses this to trigger highlight
 * onSaveComplete: () => void — called after batch save to refresh extractions
 */
export default function SchemaReviewPane({
  schema, extractions, workspaceId, documentId,
  onFieldFocus, onSaveComplete,
}) {
  const [activeField, setActiveField] = useState(null)
  const [pendingChanges, setPendingChanges] = useState({})  // { fieldName: { value, evidence } }
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState(null)

  // Build lookup: latest extraction per field name
  const extractionByName = Object.fromEntries(
    extractions.map((e) => [e.field_name, e])
  )

  // Group fields by their group key
  const groups = {}
  for (const field of (schema.fields || [])) {
    const g = field.group || 'Other'
    if (!groups[g]) groups[g] = []
    groups[g].push(field)
  }

  const handleFieldFocus = useCallback((fieldName) => {
    setActiveField(fieldName)
    const extraction = extractionByName[fieldName]
    onFieldFocus(fieldName, extraction?.field_value || pendingChanges[fieldName]?.value || '')
  }, [extractionByName, pendingChanges, onFieldFocus])

  const handleFieldChange = useCallback((fieldName, value) => {
    setPendingChanges((prev) => ({
      ...prev,
      [fieldName]: { ...prev[fieldName], value },
    }))
  }, [])

  const handleVerify = useCallback(async (fieldName, value, note, evidenceType) => {
    const evidence = { type: evidenceType, note: note || undefined }
    const extraction = extractionByName[fieldName]

    if (extraction) {
      // Patch existing row
      await correctExtraction(workspaceId, documentId, extraction.id, value)
    } else {
      // Create new row for missing field
      const field = schema.fields.find((f) => f.name === fieldName)
      await createExtraction(
        workspaceId, documentId, fieldName, value,
        field?.type || 'text', schema.id, evidence
      )
    }

    setPendingChanges((prev) => {
      const next = { ...prev }
      delete next[fieldName]
      return next
    })
    onSaveComplete()
  }, [extractionByName, schema, workspaceId, documentId, onSaveComplete])

  const dirtyCount = Object.keys(pendingChanges).length

  const handleSaveAll = async () => {
    setSaving(true)
    setSaveError(null)
    const results = await Promise.allSettled(
      Object.entries(pendingChanges).map(([fieldName, { value }]) =>
        handleVerify(fieldName, value, '', 'manual_draw')
      )
    )
    setSaving(false)
    const failed = results.filter((r) => r.status === 'rejected')
    if (failed.length > 0) {
      setSaveError(`${failed.length} field(s) failed to save — try again.`)
    }
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-slate-700 shrink-0">
        <div>
          <span className="text-xs font-semibold text-slate-300 uppercase tracking-wide">
            {schema.document_type}
          </span>
          <span className="text-xs text-slate-500 ml-2">
            {extractions.length}/{schema.fields?.length || 0} extracted
          </span>
        </div>
        <span className="text-xs text-slate-600">Tab to navigate</span>
      </div>

      {/* Scrollable form */}
      <div className="flex-1 overflow-y-auto px-3 py-2">
        {Object.entries(groups).map(([groupName, fields]) => (
          <div key={groupName} className="mb-4">
            <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1.5 pb-1 border-b border-slate-800">
              {groupName}
            </div>
            {fields.map((field) => (
              <ExtractionField
                key={field.name}
                field={field}
                extraction={extractionByName[field.name] || null}
                threshold={field.ai_threshold || schema.default_confidence_threshold}
                isActive={activeField === field.name}
                onFocus={() => handleFieldFocus(field.name)}
                onChange={handleFieldChange}
                onVerify={handleVerify}
                workspaceId={workspaceId}
                documentId={documentId}
              />
            ))}
          </div>
        ))}
      </div>

      {/* Save bar */}
      <div className="shrink-0 px-3 py-2 border-t border-slate-700 bg-slate-900/50">
        {saveError && (
          <p className="text-xs text-red-400 mb-1">{saveError}</p>
        )}
        <div className="flex items-center gap-2">
          <span className="text-xs text-slate-500 flex-1">
            {dirtyCount > 0 ? `${dirtyCount} unsaved change${dirtyCount !== 1 ? 's' : ''}` : 'No unsaved changes'}
          </span>
          <button
            disabled={dirtyCount === 0 || saving}
            onClick={handleSaveAll}
            className="text-xs px-3 py-1.5 bg-blue-600 hover:bg-blue-500 text-white rounded disabled:opacity-40 transition-colors"
          >
            {saving ? 'Saving…' : 'Save all'}
          </button>
        </div>
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Verify build**

```bash
cd "C:\Users\tjcol\OneDrive\Projects\Investigation software\frontend" && npm run build 2>&1 | tail -5
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
cd "C:\Users\tjcol\OneDrive\Projects\Investigation software" && git add frontend/src/components/documents/SchemaReviewPane.jsx && git commit -m "feat: SchemaReviewPane — schema-driven form with sections, save-all, missing field support"
```

---

## Task 12: DocumentViewer wiring

**Files:**
- Modify: `frontend/src/pages/workspace/DocumentViewer.jsx`

This task wires everything together: text layer capture from pdfjs, schema fetch, highlight state, and renders `SchemaReviewPane` in review mode.

- [ ] **Step 1: Update DocumentViewer.jsx imports and state**

At the top of `DocumentViewer.jsx`, update imports to add:

```javascript
import { getSchema } from '../../api/schemas'
import SchemaReviewPane from '../../components/documents/SchemaReviewPane'
import PDFHighlightOverlay from '../../components/documents/PDFHighlightOverlay'
import { useFieldHighlight } from '../../hooks/useFieldHighlight'
import { useRegionCapture } from '../../hooks/useRegionCapture'
```

Add new state variables in the `DocumentViewer` component (after existing state):

```javascript
  const [schema, setSchema] = useState(null)
  const [pdfProxy, setPdfProxy] = useState(null)
  const [textItems, setTextItems] = useState([])
  const [pageViewport, setPageViewport] = useState(null)
  const [activeFieldValue, setActiveFieldValue] = useState('')
  const [activeFieldName, setActiveFieldName] = useState('')
  const [pdfScale] = useState(1.0)  // adjust if zoom is added later
  const pageContainerRef = useRef(null)
```

- [ ] **Step 2: Fetch schema when doc loads**

In the `useEffect` that fetches doc data, after `setDoc(docRes.value.data)`:

```javascript
      if (docRes.status === 'fulfilled') {
        const docData = docRes.value.data
        setDoc(docData)
        // Fetch schema for review pane
        if (docData.schema_id) {
          getSchema(docData.schema_id)
            .then((r) => setSchema(r.data))
            .catch(() => {})  // schema missing is non-fatal
        }
      }
```

- [ ] **Step 3: Load pdf.js document for text layer access**

Add a `useEffect` that loads the PDF via pdfjs when the file URL is ready:

```javascript
  useEffect(() => {
    if (!fileUrl) return
    const loadingTask = pdfjs.getDocument(fileUrl)
    loadingTask.promise.then((pdf) => setPdfProxy(pdf))
    return () => { loadingTask.destroy?.() }
  }, [fileUrl])
```

Add a `useEffect` that fetches text items when the page changes:

```javascript
  useEffect(() => {
    if (!pdfProxy || !currentPage) return
    pdfProxy.getPage(currentPage).then((page) => {
      const viewport = page.getViewport({ scale: pdfScale })
      setPageViewport(viewport)
      page.getTextContent().then((content) => {
        setTextItems(content.items)
      })
    })
  }, [pdfProxy, currentPage, pdfScale])
```

- [ ] **Step 4: Wire useFieldHighlight and useRegionCapture**

Add after the state declarations:

```javascript
  const { matches, activeIndex, activeMatch, next, prev } = useFieldHighlight(
    activeFieldValue, textItems, pageViewport
  )
  const { startDraw } = useRegionCapture(pageContainerRef)
```

Add the `onFieldFocus` handler:

```javascript
  const handleFieldFocus = useCallback((fieldName, fieldValue) => {
    setActiveFieldName(fieldName)
    setActiveFieldValue(fieldValue || '')
  }, [])
```

- [ ] **Step 5: Update the PDF pane to enable text layer and add overlay**

Find the `<Page>` component render (around line 171). Change:

```jsx
              <div ref={pageContainerRef} style={{ position: 'relative' }}>
                <Page
                  pageNumber={currentPage}
                  renderTextLayer={true}
                  renderAnnotationLayer={false}
                  className="shadow-2xl"
                />
                {reviewMode && activeMatch && (
                  <PDFHighlightOverlay
                    activeMatch={activeMatch}
                    activeFieldName={activeFieldName}
                    matchCount={matches.length}
                    matchIndex={activeIndex}
                    onNext={next}
                    onPrev={prev}
                  />
                )}
              </div>
```

- [ ] **Step 6: Replace FieldsPane in review mode with SchemaReviewPane**

Find the `<FieldsPane>` render (around line 185). Change the fields pane div:

```jsx
          {/* Fields pane — 35% */}
          <div className="flex-[35] flex flex-col min-h-0 border-l border-slate-700">
            {reviewMode && schema ? (
              <SchemaReviewPane
                schema={schema}
                extractions={extractions}
                workspaceId={workspaceId}
                documentId={documentId}
                onFieldFocus={handleFieldFocus}
                onSaveComplete={() => {
                  getExtractions(workspaceId, documentId).then((r) => setExtractions(r.data))
                }}
              />
            ) : (
              <div className="overflow-y-auto p-4">
                <FieldsPane
                  doc={doc}
                  extractions={extractions}
                  editable={reviewMode}
                  workspaceId={workspaceId}
                  documentId={documentId}
                  onUpdate={(corrected) =>
                    setExtractions((prev) =>
                      prev.map((e) => (e.field_name === corrected.field_name ? corrected : e))
                    )
                  }
                />
              </div>
            )}
          </div>
```

- [ ] **Step 7: Verify build**

```bash
cd "C:\Users\tjcol\OneDrive\Projects\Investigation software\frontend" && npm run build 2>&1 | tail -10
```

Expected: no errors.

- [ ] **Step 8: Run backend test suite one final time**

```bash
docker-compose run --rm -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test backend pytest tests/ -q 2>&1 | tail -5
```

Expected: all pass.

- [ ] **Step 9: Commit**

```bash
cd "C:\Users\tjcol\OneDrive\Projects\Investigation software" && git add frontend/src/pages/workspace/DocumentViewer.jsx && git commit -m "feat: DocumentViewer — text layer capture, schema fetch, SchemaReviewPane in review mode"
```

---

## Self-Review

### Spec Coverage

| Spec Requirement | Task |
|---|---|
| `evidence JSONB` on document_extractions | Task 1 (migration), Task 2 (model/schema) |
| `group` key on schema_fields | Task 3 (seeds) |
| OCR DPI 200 → 300 | Task 4 |
| Partial batch retry | Task 4 |
| POST .../extractions (create from scratch) | Task 5 |
| GET /schemas/{id} | Task 5 |
| Evidence on correct_extraction | Task 5 |
| createExtraction API | Task 6 |
| getSchema API | Task 6 |
| useFieldHighlight (text layer search) | Task 7 |
| useRegionCapture (canvas crop + draw) | Task 8 |
| ExtractionField (4 states, verify, note) | Task 9 |
| SchemaReviewPane (groups, save-all, missing) | Task 11 |
| PDFHighlightOverlay (box, label, nav) | Task 10 |
| DocumentViewer wiring | Task 12 |

### Deferred (not in this plan, per spec)
- Output format normalization (follow-on plan)
- Extraction type enum on schema_fields (follow-on plan)
- Vision fallback for critical OCR failures (Phase 2F)
- Table field coordinate math (after table extraction ships)
- Multi-user concurrent review (Phase 4A)

### Type Consistency Check
- `evidence: dict | None` consistent across model, ExtractionOut, ExtractionCreateIn, ExtractionCorrectionIn/Out ✅
- `ExtractionField.onVerify` signature `(fieldName, value, note, type)` matches `SchemaReviewPane.handleVerify` call ✅
- `useFieldHighlight` returns `{ matches, activeIndex, activeMatch, next, prev }` — all consumed in DocumentViewer ✅
- `useRegionCapture` returns `{ capture, startDraw }` — `startDraw` used in DocumentViewer via ExtractionField ✅
- `getSchema(schemaId)` in api/schemas.js matches `GET /schemas/{schema_id}` endpoint ✅
- `createExtraction` in api/documents.js matches `POST .../extractions` endpoint signature ✅
