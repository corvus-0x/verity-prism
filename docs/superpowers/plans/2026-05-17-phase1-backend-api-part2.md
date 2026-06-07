# Phase 1 Backend API — Part 2 (Tasks 7–11)

> This file continues from `2026-05-17-phase1-backend-api.md`. Complete Tasks 1–6 before starting here.

---

## Task 7: Transactions, Leads, and Notes APIs

**What you're building:** Three smaller APIs that follow the same pattern you already know from workspaces and entities. Build them together — one commit for all three.

**Files:**
- Create: `backend/app/schemas/transaction.py`
- Create: `backend/app/routers/transactions.py`
- Create: `backend/app/schemas/lead.py`
- Create: `backend/app/routers/leads.py`
- Create: `backend/app/schemas/note.py`
- Create: `backend/app/routers/notes.py`
- Create: `backend/tests/test_transactions.py`
- Create: `backend/tests/test_leads.py`
- Create: `backend/tests/test_notes.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Write failing tests — `backend/tests/test_transactions.py`**

```python
import pytest

@pytest.fixture
def workspace_id(client, auth_headers):
    return client.post("/workspaces/", json={"name": "Test", "vertical": "fraud"},
                       headers=auth_headers).json()["id"]

def test_create_transaction(client, auth_headers, workspace_id):
    response = client.post(f"/workspaces/{workspace_id}/transactions", json={
        "transaction_type": "purchase",
        "amount_paid": 300000,
        "appraised_value": 37490,
        "consideration": "above_market",
        "transaction_date": "2022-09-15",
        "instrument_number": "202300004871",
        "notes": "47 Sycamore St — Seller: Winner Kyle J"
    }, headers=auth_headers)
    assert response.status_code == 201
    data = response.json()
    assert float(data["amount_paid"]) == 300000.0
    assert data["consideration"] == "above_market"

def test_list_transactions(client, auth_headers, workspace_id):
    client.post(f"/workspaces/{workspace_id}/transactions",
                json={"transaction_type": "transfer", "amount_paid": 0,
                      "consideration": "zero"}, headers=auth_headers)
    response = client.get(f"/workspaces/{workspace_id}/transactions", headers=auth_headers)
    assert response.status_code == 200
    assert len(response.json()) == 1
```

- [ ] **Step 2: Write failing tests — `backend/tests/test_leads.py`**

```python
import pytest

@pytest.fixture
def workspace_id(client, auth_headers):
    return client.post("/workspaces/", json={"name": "Test", "vertical": "fraud"},
                       headers=auth_headers).json()["id"]

def test_create_lead(client, auth_headers, workspace_id):
    response = client.post(f"/workspaces/{workspace_id}/leads", json={
        "question": "Does Sarah Mitchell have related businesses registered in Ohio?",
        "source": "Ohio Secretary of State"
    }, headers=auth_headers)
    assert response.status_code == 201
    assert response.json()["status"] == "pending"

def test_complete_lead_with_summary(client, auth_headers, workspace_id):
    lead = client.post(f"/workspaces/{workspace_id}/leads",
                       json={"question": "Test question"}, headers=auth_headers).json()
    response = client.patch(f"/workspaces/{workspace_id}/leads/{lead['id']}", json={
        "status": "complete",
        "result_summary": "Found Bright Future Real Estate LLC (SOS #7654321)"
    }, headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["status"] == "complete"
    assert response.json()["result_summary"] is not None
```

- [ ] **Step 3: Write failing tests — `backend/tests/test_notes.py`**

```python
import pytest

@pytest.fixture
def workspace_id(client, auth_headers):
    return client.post("/workspaces/", json={"name": "Test"},
                       headers=auth_headers).json()["id"]

def test_create_note(client, auth_headers, workspace_id):
    response = client.post(f"/workspaces/{workspace_id}/notes", json={
        "entity_type": "workspace",
        "entity_id": workspace_id,
        "content": "Address digit sequence reversed — 6172 vs 6712 Olding Rd. Same road as nonprofit."
    }, headers=auth_headers)
    assert response.status_code == 201
    assert "reversed" in response.json()["content"]

def test_list_notes_filtered_by_entity(client, auth_headers, workspace_id):
    client.post(f"/workspaces/{workspace_id}/notes",
                json={"entity_type": "workspace", "entity_id": workspace_id, "content": "Note 1"},
                headers=auth_headers)
    response = client.get(
        f"/workspaces/{workspace_id}/notes?entity_type=workspace&entity_id={workspace_id}",
        headers=auth_headers
    )
    assert response.status_code == 200
    assert len(response.json()) == 1
```

- [ ] **Step 4: Run all three test files to confirm they fail**

```bash
pytest tests/test_transactions.py tests/test_leads.py tests/test_notes.py -v
```

- [ ] **Step 5: Create `backend/app/schemas/transaction.py`**

```python
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, date

class TransactionCreate(BaseModel):
    transaction_type: str
    entity_from_id: Optional[str] = None
    entity_to_id: Optional[str] = None
    amount_paid: Optional[float] = None
    appraised_value: Optional[float] = None
    consideration: Optional[str] = None
    transaction_date: Optional[date] = None
    recorded_date: Optional[date] = None
    instrument_number: Optional[str] = None
    source_doc_id: Optional[str] = None
    notes: Optional[str] = None

class TransactionOut(BaseModel):
    id: str
    workspace_id: str
    transaction_type: str
    amount_paid: Optional[float]
    appraised_value: Optional[float]
    consideration: Optional[str]
    transaction_date: Optional[date]
    instrument_number: Optional[str]
    notes: Optional[str]
    created_at: datetime
    class Config:
        from_attributes = True
```

- [ ] **Step 6: Create `backend/app/schemas/lead.py`**

```python
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class LeadCreate(BaseModel):
    question: str
    source: Optional[str] = None
    originated_by: str = "user"
    triggered_by_id: Optional[str] = None
    assigned_to: Optional[str] = None

class LeadUpdate(BaseModel):
    status: Optional[str] = None
    result_summary: Optional[str] = None
    source: Optional[str] = None

class LeadOut(BaseModel):
    id: str
    workspace_id: str
    question: str
    source: Optional[str]
    status: str
    originated_by: str
    triggered_by_id: Optional[str]
    result_summary: Optional[str]
    created_at: datetime
    class Config:
        from_attributes = True
```

- [ ] **Step 7: Create `backend/app/schemas/note.py`**

```python
from pydantic import BaseModel
from datetime import datetime

class NoteCreate(BaseModel):
    entity_type: str
    entity_id: str
    content: str

class NoteOut(BaseModel):
    id: str
    workspace_id: str
    entity_type: str
    entity_id: str
    content: str
    created_at: datetime
    class Config:
        from_attributes = True
```

- [ ] **Step 8: Create `backend/app/routers/transactions.py`**

```python
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.transaction import Transaction
from app.models.user import User
from app.schemas.transaction import TransactionCreate, TransactionOut
from app.services.auth import get_current_user
from app.services import audit
from app.routers.workspaces import get_workspace_or_404

router = APIRouter(prefix="/workspaces/{workspace_id}/transactions", tags=["transactions"])

@router.post("/", response_model=TransactionOut, status_code=201)
def create_transaction(workspace_id: str, payload: TransactionCreate,
                       db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    get_workspace_or_404(workspace_id, user, db)
    tx = Transaction(**payload.model_dump(), workspace_id=workspace_id, created_by=user.id)
    db.add(tx)
    db.commit()
    db.refresh(tx)
    audit.log(db, action="created", user_id=user.id, workspace_id=workspace_id,
              entity_type="transaction", entity_id=tx.id,
              after_state={"type": tx.transaction_type, "amount": str(tx.amount_paid)})
    return tx

@router.get("/", response_model=list[TransactionOut])
def list_transactions(workspace_id: str, db: Session = Depends(get_db),
                      user: User = Depends(get_current_user)):
    get_workspace_or_404(workspace_id, user, db)
    return db.query(Transaction).filter(Transaction.workspace_id == workspace_id).all()
```

- [ ] **Step 9: Create `backend/app/routers/leads.py`**

```python
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.lead import InvestigationLead
from app.models.user import User
from app.schemas.lead import LeadCreate, LeadUpdate, LeadOut
from app.services.auth import get_current_user
from app.services import audit
from app.routers.workspaces import get_workspace_or_404

router = APIRouter(prefix="/workspaces/{workspace_id}/leads", tags=["leads"])

@router.post("/", response_model=LeadOut, status_code=201)
def create_lead(workspace_id: str, payload: LeadCreate,
                db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    get_workspace_or_404(workspace_id, user, db)
    lead = InvestigationLead(**payload.model_dump(), workspace_id=workspace_id)
    db.add(lead)
    db.commit()
    db.refresh(lead)
    audit.log(db, action="created", user_id=user.id, workspace_id=workspace_id,
              entity_type="lead", entity_id=lead.id)
    return lead

@router.get("/", response_model=list[LeadOut])
def list_leads(workspace_id: str, db: Session = Depends(get_db),
               user: User = Depends(get_current_user)):
    get_workspace_or_404(workspace_id, user, db)
    return db.query(InvestigationLead).filter(
        InvestigationLead.workspace_id == workspace_id
    ).all()

@router.patch("/{lead_id}", response_model=LeadOut)
def update_lead(workspace_id: str, lead_id: str, payload: LeadUpdate,
                db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    get_workspace_or_404(workspace_id, user, db)
    lead = db.query(InvestigationLead).filter(
        InvestigationLead.id == lead_id, InvestigationLead.workspace_id == workspace_id
    ).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(lead, field, value)
    if payload.status in ("complete", "dead_end"):
        lead.completed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(lead)
    audit.log(db, action="updated", user_id=user.id, workspace_id=workspace_id,
              entity_type="lead", entity_id=lead.id)
    return lead
```

- [ ] **Step 10: Create `backend/app/routers/notes.py`**

```python
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import Optional
from app.database import get_db
from app.models.note import Note
from app.models.user import User
from app.schemas.note import NoteCreate, NoteOut
from app.services.auth import get_current_user
from app.routers.workspaces import get_workspace_or_404

router = APIRouter(prefix="/workspaces/{workspace_id}/notes", tags=["notes"])

@router.post("/", response_model=NoteOut, status_code=201)
def create_note(workspace_id: str, payload: NoteCreate,
                db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    get_workspace_or_404(workspace_id, user, db)
    note = Note(**payload.model_dump(), workspace_id=workspace_id, author_id=user.id)
    db.add(note)
    db.commit()
    db.refresh(note)
    return note

@router.get("/", response_model=list[NoteOut])
def list_notes(workspace_id: str,
               entity_type: Optional[str] = None,
               entity_id: Optional[str] = None,
               db: Session = Depends(get_db),
               user: User = Depends(get_current_user)):
    get_workspace_or_404(workspace_id, user, db)
    q = db.query(Note).filter(Note.workspace_id == workspace_id)
    if entity_type:
        q = q.filter(Note.entity_type == entity_type)
    if entity_id:
        q = q.filter(Note.entity_id == entity_id)
    return q.all()
```

- [ ] **Step 11: Register all three routers in `main.py`**

```python
from app.routers import auth, workspaces, entities, findings, transactions, leads, notes
app.include_router(transactions.router)
app.include_router(leads.router)
app.include_router(notes.router)
```

- [ ] **Step 12: Run all tests**

```bash
pytest tests/test_transactions.py tests/test_leads.py tests/test_notes.py -v
```

Expected: 6 tests PASS.

- [ ] **Step 13: Commit**

```bash
git add backend/app/schemas/transaction.py backend/app/schemas/lead.py \
        backend/app/schemas/note.py backend/app/routers/transactions.py \
        backend/app/routers/leads.py backend/app/routers/notes.py \
        backend/app/main.py backend/tests/
git commit -m "feat: transactions, investigation leads, and notes APIs"
```

---

## Task 8: Document Pipeline + Extraction Engine

**What you're building:** The heart of the IDP platform. This is the most complex task — read it fully before starting.

**The pipeline runs in this order, every time a document is uploaded:**
1. Hash the file (evidence lock)
2. Store it on disk
3. OCR it (read the text)
4. Detect the document type
5. Extract every field defined in the schema
6. Generate a standardized filename
7. Update the search index
8. Save everything to the database

**Why is the hash first?** Because the hash proves the original file is unchanged. If you ran OCR first and then hashed, the hash would prove nothing useful.

**Files:**
- Create: `backend/app/services/ocr.py`
- Create: `backend/app/services/extraction_engine.py`
- Create: `backend/app/services/naming.py`
- Create: `backend/app/services/document_pipeline.py`
- Create: `backend/app/schemas/document.py`
- Create: `backend/app/routers/documents.py`
- Create: `backend/tests/test_documents.py`
- Create: `backend/tests/test_extractions.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Write failing tests — `backend/tests/test_documents.py`**

```python
import pytest
import io

@pytest.fixture
def workspace_id(client, auth_headers):
    return client.post("/workspaces/", json={"name": "Test"},
                       headers=auth_headers).json()["id"]

def test_upload_creates_document_record(client, auth_headers, workspace_id):
    content = b"%PDF-1.4 test content"
    response = client.post(
        f"/workspaces/{workspace_id}/documents",
        files={"file": ("test_deed.pdf", io.BytesIO(content), "application/pdf")},
        headers=auth_headers
    )
    assert response.status_code == 201
    data = response.json()
    assert data["original_filename"] == "test_deed.pdf"
    assert len(data["sha256_hash"]) == 64  # SHA-256 hex is always 64 characters
    assert data["extraction_status"] in ("pending", "complete", "failed")

def test_original_filename_is_preserved(client, auth_headers, workspace_id):
    content = b"some content"
    response = client.post(
        f"/workspaces/{workspace_id}/documents",
        files={"file": ("My Weird File Name (copy).pdf", io.BytesIO(content), "application/pdf")},
        headers=auth_headers
    )
    assert response.status_code == 201
    # The standardized filename changes, but original_filename never does
    assert response.json()["original_filename"] == "My Weird File Name (copy).pdf"

def test_same_content_produces_same_hash(client, auth_headers, workspace_id):
    content = b"identical file content"
    r1 = client.post(f"/workspaces/{workspace_id}/documents",
                     files={"file": ("a.pdf", io.BytesIO(content), "application/pdf")},
                     headers=auth_headers)
    r2 = client.post(f"/workspaces/{workspace_id}/documents",
                     files={"file": ("b.pdf", io.BytesIO(content), "application/pdf")},
                     headers=auth_headers)
    assert r1.json()["sha256_hash"] == r2.json()["sha256_hash"]

def test_list_documents(client, auth_headers, workspace_id):
    content = b"test"
    client.post(f"/workspaces/{workspace_id}/documents",
                files={"file": ("doc.pdf", io.BytesIO(content), "application/pdf")},
                headers=auth_headers)
    response = client.get(f"/workspaces/{workspace_id}/documents", headers=auth_headers)
    assert response.status_code == 200
    assert len(response.json()) == 1
```

- [ ] **Step 2: Write failing tests — `backend/tests/test_extractions.py`**

```python
import pytest
import io
from unittest.mock import patch, MagicMock

@pytest.fixture
def workspace_id(client, auth_headers):
    return client.post("/workspaces/", json={"name": "Test"},
                       headers=auth_headers).json()["id"]

def test_extractions_created_after_upload(client, auth_headers, workspace_id):
    """
    When a document is uploaded and extracted, at least one extraction row
    should exist for it. We mock Claude so the test doesn't need a real API key.
    """
    content = b"%PDF-1.4 Grantor: Sarah Mitchell. Grantee: Bright Future Real Estate LLC. Amount: $300,000."

    with patch("app.services.extraction_engine.Anthropic") as mock_anthropic:
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client
        # Mock detect_document_type response
        mock_client.messages.create.return_value = MagicMock(
            content=[MagicMock(text='{"document_type": "DEED"}')]
        )

        response = client.post(
            f"/workspaces/{workspace_id}/documents",
            files={"file": ("deed.pdf", io.BytesIO(content), "application/pdf")},
            headers=auth_headers
        )

    assert response.status_code == 201
    doc_id = response.json()["id"]

    extractions = client.get(
        f"/workspaces/{workspace_id}/documents/{doc_id}/extractions",
        headers=auth_headers
    )
    assert extractions.status_code == 200
    # Even a mocked extraction should produce at least one row
    assert isinstance(extractions.json(), list)
```

- [ ] **Step 3: Run tests to confirm they fail**

```bash
pytest tests/test_documents.py tests/test_extractions.py -v
```

- [ ] **Step 4: Create `backend/app/services/ocr.py`**

```python
import fitz  # PyMuPDF
import pytesseract
from PIL import Image
import io

def extract_text_from_pdf(file_bytes: bytes) -> str:
    """
    Extract all text from a PDF.
    First tries to get embedded text (fast, accurate).
    If a page has no embedded text, it's probably a scanned image —
    render it and run OCR (slower but handles scanned documents).
    """
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    pages = []
    for page in doc:
        text = page.get_text().strip()
        if text:
            pages.append(text)
        else:
            # Scanned page — render at 200 DPI for good OCR quality
            pix = page.get_pixmap(dpi=200)
            img = Image.open(io.BytesIO(pix.tobytes("png")))
            ocr_text = pytesseract.image_to_string(img)
            pages.append(ocr_text.strip())
    doc.close()
    return "\n\n--- PAGE BREAK ---\n\n".join(pages)

def extract_text_from_image(file_bytes: bytes) -> str:
    img = Image.open(io.BytesIO(file_bytes))
    return pytesseract.image_to_string(img)

def extract_text(file_bytes: bytes, file_type: str) -> str:
    """Main entry point — extract text from any supported file type."""
    if file_type == "pdf":
        return extract_text_from_pdf(file_bytes)
    elif file_type == "image":
        return extract_text_from_image(file_bytes)
    elif file_type in ("text", "csv", "xml"):
        return file_bytes.decode("utf-8", errors="replace")
    return ""
```

- [ ] **Step 5: Create `backend/app/services/extraction_engine.py`**

```python
import json
import re
from anthropic import Anthropic
from sqlalchemy.orm import Session
from app.config import settings
from app.models.document_schema import DocumentSchema
from app.models.document_extraction import DocumentExtraction

client = Anthropic(api_key=settings.anthropic_api_key)

# Document types the system knows about.
# When Claude detects a type not in this list, it falls back to "OTHER".
KNOWN_DOCUMENT_TYPES = [
    "DEED", "990", "990-T", "UCC", "SOS-FILING", "BUILDING-PERMIT",
    "INSURANCE-FORM", "COURT-FILING", "AUDIT-REPORT", "CORRESPONDENCE",
    "OBITUARY", "NEWS-ARTICLE", "SCREENSHOT", "SPREADSHEET", "OTHER"
]

def detect_document_type(ocr_text: str) -> str:
    """
    Ask Claude to identify what kind of document this is.
    Returns one of the KNOWN_DOCUMENT_TYPES.
    """
    prompt = f"""You are analyzing a document to determine its type.
Based on the text below, identify the document type.

Choose EXACTLY ONE from this list:
{', '.join(KNOWN_DOCUMENT_TYPES)}

Respond with JSON only: {{"document_type": "TYPE_HERE"}}

Document text (first 1500 characters):
{ocr_text[:1500]}"""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=50,
            messages=[{"role": "user", "content": prompt}]
        )
        result = json.loads(response.content[0].text.strip())
        detected = result.get("document_type", "OTHER")
        return detected if detected in KNOWN_DOCUMENT_TYPES else "OTHER"
    except Exception:
        return "OTHER"

def get_schema_for_type(doc_type: str, db: Session) -> DocumentSchema | None:
    """Look up the extraction schema for this document type."""
    return db.query(DocumentSchema).filter(
        DocumentSchema.document_type == doc_type,
        DocumentSchema.is_active == True
    ).first()

def extract_fields(ocr_text: str, schema: DocumentSchema) -> list[dict]:
    """
    Ask Claude to extract every field defined in the schema.

    Returns a list of dicts like:
    [
        {"field_name": "grantor_name", "field_value": "Sarah Mitchell",
         "field_type": "name", "confidence": 0.95},
        {"field_name": "consideration_amount", "field_value": "300000.00",
         "field_type": "currency", "confidence": 0.99},
        ...
    ]
    """
    fields_description = "\n".join([
        f"- {f['name']} ({f['type']}): {f['description']}"
        for f in schema.schema_fields
    ])

    prompt = f"""{schema.extraction_prompt or 'Extract the following fields from this document.'}

Fields to extract:
{fields_description}

For each field, provide:
- field_name: the exact field name from the list above
- field_value: the extracted value as a string (null if not found)
- field_type: the type (name/date/currency/address/id_number/text/boolean)
- confidence: 0.0 to 1.0 (how confident you are in this extraction)

Respond with JSON only:
{{"extractions": [
    {{"field_name": "...", "field_value": "...", "field_type": "...", "confidence": 0.95}},
    ...
]}}

Document text:
{ocr_text[:4000]}"""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}]
        )
        result = json.loads(response.content[0].text.strip())
        return result.get("extractions", [])
    except Exception:
        return []

def save_extractions(
    extractions: list[dict],
    document_id: str,
    workspace_id: str,
    schema_id: str,
    db: Session
):
    """Save each extracted field as one row in document_extractions."""
    for item in extractions:
        if not item.get("field_name"):
            continue
        row = DocumentExtraction(
            document_id=document_id,
            workspace_id=workspace_id,
            field_name=item["field_name"],
            field_value=item.get("field_value"),
            field_type=item.get("field_type", "text"),
            confidence=item.get("confidence", 1.0),
            schema_id=schema_id,
        )
        db.add(row)
    db.commit()
```

- [ ] **Step 6: Create `backend/app/services/naming.py`**

```python
import re
from anthropic import Anthropic
from app.config import settings

client = Anthropic(api_key=settings.anthropic_api_key)

DOC_TYPE_CODES = [
    "DEED", "990", "990-T", "UCC", "SOS-FILING", "BUILDING-PERMIT",
    "INSURANCE-FORM", "COURT-FILING", "AUDIT-REPORT", "CORRESPONDENCE",
    "OBITUARY", "NEWS-ARTICLE", "SCREENSHOT", "SPREADSHEET", "OTHER"
]

def generate_standardized_name(ocr_text: str, original_filename: str, file_ext: str) -> str:
    """
    Ask Claude to generate a standardized filename.
    Format: YYYY-MM-DD_DOC-TYPE_PRIMARY-ENTITY_BRIEF-DESCRIPTION.ext
    """
    prompt = f"""Generate a standardized filename for this investigative document.

Format: YYYY-MM-DD_DOC-TYPE_PRIMARY-ENTITY_BRIEF-DESCRIPTION.{file_ext}

Rules:
- DATE: Most prominent date in the document. Use UNKNOWN-DATE if none found.
- DOC-TYPE: Choose from: {', '.join(DOC_TYPE_CODES)}
- PRIMARY-ENTITY: Main organization or person. CamelCase, no spaces.
- BRIEF-DESCRIPTION: 2-5 words, hyphens only, no spaces.
- Only letters, numbers, hyphens, underscores, and dots.

Original filename: {original_filename}

Document text (first 1500 chars):
{ocr_text[:1500]}

Respond with ONLY the filename. No explanation."""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=100,
            messages=[{"role": "user", "content": prompt}]
        )
        name = response.content[0].text.strip()
        # Remove any characters that are unsafe in filenames
        name = re.sub(r"[^\w\-.]", "", name)
        return name if name else f"UNKNOWN-DATE_OTHER_{original_filename}"
    except Exception:
        return f"UNKNOWN-DATE_OTHER_{original_filename}"
```

- [ ] **Step 7: Create `backend/app/services/document_pipeline.py`**

```python
import hashlib
import uuid
from pathlib import Path
from fastapi import UploadFile
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.config import settings
from app.models.document import Document
from app.services.ocr import extract_text
from app.services.extraction_engine import (
    detect_document_type, get_schema_for_type,
    extract_fields, save_extractions
)
from app.services.naming import generate_standardized_name
from app.services import audit

# Map file extensions to our file_type enum values
EXTENSION_TO_TYPE = {
    ".pdf": "pdf", ".png": "image", ".jpg": "image", ".jpeg": "image",
    ".tiff": "image", ".tif": "image", ".csv": "csv",
    ".txt": "text", ".xml": "xml",
}

def process_upload(file: UploadFile, workspace_id: str, user_id: str, db: Session) -> Document:
    """
    The full document ingestion pipeline. Steps run in this exact order:
    1. Hash (evidence lock — must be first)
    2. Store file
    3. OCR
    4. Detect document type
    5. Extract fields using schema
    6. Generate standardized name
    7. Update search index
    8. Save document record
    9. Audit log
    """

    # Step 1: Read file and generate hash IMMEDIATELY
    # This must happen before anything else touches the file.
    file_bytes = file.file.read()
    sha256_hash = hashlib.sha256(file_bytes).hexdigest()

    # Step 2: Determine file type and store to disk
    ext = Path(file.filename).suffix.lower()
    file_type = EXTENSION_TO_TYPE.get(ext, "other")

    upload_dir = Path(settings.upload_dir) / workspace_id
    upload_dir.mkdir(parents=True, exist_ok=True)
    stored_name = f"{uuid.uuid4()}{ext}"
    file_path = upload_dir / stored_name
    file_path.write_bytes(file_bytes)

    # Step 3: OCR — extract all text from the file
    ocr_text = extract_text(file_bytes, file_type)

    # Step 4: Ask Claude what type of document this is
    doc_type = detect_document_type(ocr_text)

    # Step 5: Get the schema for this document type and extract fields
    schema = get_schema_for_type(doc_type, db)

    # Step 6: Generate a standardized filename
    standardized_name = generate_standardized_name(ocr_text, file.filename, ext.lstrip(".") or "pdf")

    # Step 7: Build the search vector string (full text + field values concatenated)
    # This gets stored as a tsvector in PostgreSQL for fast full-text search.
    search_content = ocr_text

    # Step 8: Create the document record in the database
    doc = Document(
        workspace_id=workspace_id,
        filename=standardized_name,
        original_filename=file.filename,
        file_path=str(file_path),
        file_type=file_type,
        sha256_hash=sha256_hash,
        source_type="upload",
        detected_doc_type=doc_type,
        schema_id=schema.id if schema else None,
        ocr_text=ocr_text,
        search_vector=search_content,  # Will be converted to tsvector by trigger
        size_bytes=len(file_bytes),
        extraction_status="pending",
        uploaded_by=user_id,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    # Run extraction and update the search vector with extracted field values
    if schema:
        extractions = extract_fields(ocr_text, schema)
        save_extractions(extractions, doc.id, workspace_id, schema.id, db)

        # Add extracted field values to the search content
        extra_search_content = " ".join([
            f"{e['field_name']} {e.get('field_value', '')}"
            for e in extractions if e.get("field_value")
        ])
        # Update search_vector with full content including extractions
        db.execute(
            text("UPDATE documents SET search_vector = to_tsvector('english', :content), "
                 "extraction_status = 'complete' WHERE id = :doc_id"),
            {"content": f"{ocr_text} {extra_search_content}", "doc_id": doc.id}
        )
    else:
        # No schema — still index the OCR text
        db.execute(
            text("UPDATE documents SET search_vector = to_tsvector('english', :content), "
                 "extraction_status = 'complete' WHERE id = :doc_id"),
            {"content": ocr_text, "doc_id": doc.id}
        )
    db.commit()
    db.refresh(doc)

    # Step 9: Audit log
    audit.log(
        db, action="uploaded", user_id=user_id, workspace_id=workspace_id,
        entity_type="document", entity_id=doc.id,
        after_state={
            "filename": standardized_name,
            "hash": sha256_hash,
            "doc_type": doc_type,
            "source": "upload"
        }
    )

    return doc
```

- [ ] **Step 8: Create `backend/app/schemas/document.py`**

```python
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class DocumentOut(BaseModel):
    id: str
    workspace_id: str
    filename: str
    original_filename: str
    file_type: str
    sha256_hash: str
    source_url: Optional[str]
    source_type: str
    detected_doc_type: Optional[str]
    extraction_status: str
    size_bytes: Optional[int]
    uploaded_at: datetime
    class Config:
        from_attributes = True

class ExtractionOut(BaseModel):
    id: str
    document_id: str
    field_name: str
    field_value: Optional[str]
    field_type: str
    confidence: float
    extracted_at: datetime
    class Config:
        from_attributes = True
```

- [ ] **Step 9: Create `backend/app/routers/documents.py`**

```python
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.document import Document
from app.models.document_extraction import DocumentExtraction
from app.models.user import User
from app.schemas.document import DocumentOut, ExtractionOut
from app.services.auth import get_current_user
from app.services.document_pipeline import process_upload
from app.routers.workspaces import get_workspace_or_404

router = APIRouter(prefix="/workspaces/{workspace_id}", tags=["documents"])

@router.post("/documents", response_model=DocumentOut, status_code=201)
def upload_document(
    workspace_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    get_workspace_or_404(workspace_id, user, db)
    return process_upload(file, workspace_id, user.id, db)

@router.get("/documents", response_model=list[DocumentOut])
def list_documents(workspace_id: str, db: Session = Depends(get_db),
                   user: User = Depends(get_current_user)):
    get_workspace_or_404(workspace_id, user, db)
    return db.query(Document).filter(Document.workspace_id == workspace_id).all()

@router.get("/documents/{document_id}", response_model=DocumentOut)
def get_document(workspace_id: str, document_id: str,
                 db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    get_workspace_or_404(workspace_id, user, db)
    doc = db.query(Document).filter(
        Document.id == document_id, Document.workspace_id == workspace_id
    ).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc

@router.get("/documents/{document_id}/extractions", response_model=list[ExtractionOut])
def list_extractions(workspace_id: str, document_id: str,
                     db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    get_workspace_or_404(workspace_id, user, db)
    return db.query(DocumentExtraction).filter(
        DocumentExtraction.document_id == document_id
    ).all()
```

- [ ] **Step 10: Register in `main.py`**

```python
from app.routers import auth, workspaces, entities, findings, transactions, leads, notes, documents
app.include_router(documents.router)
```

- [ ] **Step 11: Run tests**

```bash
pytest tests/test_documents.py tests/test_extractions.py -v
```

Expected: All tests PASS. The extraction test mocks Claude so it doesn't need a real API key.

- [ ] **Step 12: Commit**

```bash
git add backend/app/services/ocr.py backend/app/services/extraction_engine.py \
        backend/app/services/naming.py backend/app/services/document_pipeline.py \
        backend/app/schemas/document.py backend/app/routers/documents.py \
        backend/app/main.py backend/tests/
git commit -m "feat: document pipeline with SHA-256 hashing, OCR, AI extraction, and search indexing"
```

---

## Task 9: NLP Search Service

**What you're building:** The plain-English search feature. Users type a question; Claude translates it into a database query; results come back as document cards.

**How it works:**
1. User types: *"find all deeds where someone paid more than $100,000"*
2. Claude reads the query + the list of known field names
3. Claude returns structured filters
4. Backend runs a PostgreSQL query combining FTS and field filters
5. Results returned with matching field values highlighted

**Files:**
- Create: `backend/app/services/search_service.py`
- Create: `backend/app/routers/search.py`
- Create: `backend/tests/test_search.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Write failing tests — `backend/tests/test_search.py`**

```python
import pytest
import io
from unittest.mock import patch, MagicMock

@pytest.fixture
def workspace_id(client, auth_headers):
    return client.post("/workspaces/", json={"name": "Test"},
                       headers=auth_headers).json()["id"]

def test_search_endpoint_exists(client, auth_headers, workspace_id):
    response = client.post(f"/workspaces/{workspace_id}/search",
                           json={"query": "Sarah Mitchell"},
                           headers=auth_headers)
    assert response.status_code == 200
    assert "results" in response.json()
    assert "query" in response.json()

def test_empty_workspace_returns_empty_results(client, auth_headers, workspace_id):
    response = client.post(f"/workspaces/{workspace_id}/search",
                           json={"query": "anything"},
                           headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["results"] == []

def test_search_is_audit_logged(client, auth_headers, workspace_id, db):
    from app.models.audit import AuditLog
    client.post(f"/workspaces/{workspace_id}/search",
                json={"query": "test search"}, headers=auth_headers)
    log_entry = db.query(AuditLog).filter(AuditLog.action == "searched").first()
    assert log_entry is not None
```

- [ ] **Step 2: Create `backend/app/services/search_service.py`**

```python
import json
from anthropic import Anthropic
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.config import settings
from app.models.document_extraction import DocumentExtraction
from app.models.document import Document

client = Anthropic(api_key=settings.anthropic_api_key)

def get_known_field_names(workspace_id: str, db: Session) -> list[str]:
    """
    Get all unique field names that have been extracted in this workspace.
    This tells Claude what fields it can filter on.
    """
    results = db.query(DocumentExtraction.field_name).filter(
        DocumentExtraction.workspace_id == workspace_id
    ).distinct().all()
    return [r[0] for r in results]

def translate_query(natural_language_query: str, field_names: list[str]) -> dict:
    """
    Ask Claude to translate a plain English query into structured database filters.

    Returns a dict like:
    {
        "fts_query": "Sarah Mitchell deed",
        "field_filters": [
            {"field_name": "consideration_amount", "operator": "gt", "value": "100000"}
        ],
        "doc_type_filter": "DEED"
    }
    """
    fields_context = ", ".join(field_names) if field_names else "no fields extracted yet"

    prompt = f"""You translate plain English document search queries into structured database filters.

Available extracted field names in this workspace: {fields_context}

For the query below, return JSON with:
- "fts_query": keywords to search in full document text (string, can be empty "")
- "field_filters": list of field-level filters, each with:
    - "field_name": one of the available field names above
    - "operator": "eq" (equals), "contains" (text contains), "gt" (greater than), "lt" (less than)
    - "value": the value to compare against (always a string)
- "doc_type_filter": a specific document type to filter by (or null for all types)

Query: "{natural_language_query}"

Respond with JSON only. Example:
{{
    "fts_query": "Sarah Mitchell",
    "field_filters": [{{"field_name": "consideration_amount", "operator": "gt", "value": "100000"}}],
    "doc_type_filter": "DEED"
}}"""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}]
        )
        return json.loads(response.content[0].text.strip())
    except Exception:
        # If translation fails, fall back to a simple text search
        return {"fts_query": natural_language_query, "field_filters": [], "doc_type_filter": None}

def run_search(workspace_id: str, query_plan: dict, db: Session) -> list[dict]:
    """
    Execute the search against PostgreSQL.
    Combines full-text search with field-level filters.
    Returns a list of matching documents with their matched fields.
    """
    fts_query = query_plan.get("fts_query", "")
    field_filters = query_plan.get("field_filters", [])
    doc_type_filter = query_plan.get("doc_type_filter")

    # Start with all documents in this workspace
    doc_query = db.query(Document).filter(Document.workspace_id == workspace_id)

    # Apply full-text search if there's a text query
    if fts_query:
        doc_query = doc_query.filter(
            text("search_vector @@ plainto_tsquery('english', :query)").bindparams(query=fts_query)
        )

    # Apply document type filter
    if doc_type_filter:
        doc_query = doc_query.filter(Document.detected_doc_type == doc_type_filter)

    matching_docs = doc_query.limit(50).all()

    # Apply field-level filters using document_extractions
    if field_filters:
        filtered_doc_ids = set()
        first_filter = True
        for f in field_filters:
            extraction_query = db.query(DocumentExtraction.document_id).filter(
                DocumentExtraction.workspace_id == workspace_id,
                DocumentExtraction.field_name == f["field_name"]
            )
            op = f.get("operator", "eq")
            val = f.get("value", "")
            if op == "eq":
                extraction_query = extraction_query.filter(DocumentExtraction.field_value == val)
            elif op == "contains":
                extraction_query = extraction_query.filter(DocumentExtraction.field_value.ilike(f"%{val}%"))
            elif op == "gt":
                extraction_query = extraction_query.filter(
                    text("CAST(field_value AS NUMERIC) > :val").bindparams(val=float(val))
                )
            elif op == "lt":
                extraction_query = extraction_query.filter(
                    text("CAST(field_value AS NUMERIC) < :val").bindparams(val=float(val))
                )

            ids = {r[0] for r in extraction_query.all()}
            if first_filter:
                filtered_doc_ids = ids
                first_filter = False
            else:
                filtered_doc_ids &= ids  # AND logic — must match all filters

        if field_filters:
            matching_docs = [d for d in matching_docs if d.id in filtered_doc_ids]
            if not matching_docs and filtered_doc_ids:
                # FTS returned nothing but field filters matched — fetch those docs
                matching_docs = db.query(Document).filter(
                    Document.id.in_(filtered_doc_ids)
                ).limit(50).all()

    # Build result objects with matched field values
    results = []
    for doc in matching_docs:
        extractions = db.query(DocumentExtraction).filter(
            DocumentExtraction.document_id == doc.id
        ).all()
        matched_fields = {e.field_name: e.field_value for e in extractions}

        results.append({
            "document_id": doc.id,
            "filename": doc.filename,
            "original_filename": doc.original_filename,
            "detected_doc_type": doc.detected_doc_type,
            "uploaded_at": doc.uploaded_at.isoformat(),
            "matched_fields": matched_fields,
        })

    return results
```

- [ ] **Step 3: Create `backend/app/routers/search.py`**

```python
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from app.database import get_db
from app.models.user import User
from app.services.auth import get_current_user
from app.services.search_service import get_known_field_names, translate_query, run_search
from app.services import audit
from app.routers.workspaces import get_workspace_or_404

router = APIRouter(prefix="/workspaces/{workspace_id}/search", tags=["search"])

class SearchRequest(BaseModel):
    query: str

@router.post("/")
def search(
    workspace_id: str,
    payload: SearchRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    get_workspace_or_404(workspace_id, user, db)

    # Get the field names that have been extracted in this workspace
    # so Claude knows what it can filter on
    field_names = get_known_field_names(workspace_id, db)

    # Ask Claude to translate the plain English query
    query_plan = translate_query(payload.query, field_names)

    # Run the actual search
    results = run_search(workspace_id, query_plan, db)

    # Log the search for the audit trail
    audit.log(
        db, action="searched", user_id=user.id, workspace_id=workspace_id,
        entity_type="search",
        after_state={"query": payload.query, "result_count": len(results)}
    )

    return {
        "query": payload.query,
        "query_plan": query_plan,
        "result_count": len(results),
        "results": results,
    }
```

- [ ] **Step 4: Register in `main.py`**

```python
from app.routers import auth, workspaces, entities, findings, transactions, leads, notes, documents, search
app.include_router(search.router)
```

- [ ] **Step 5: Run tests**

```bash
pytest tests/test_search.py -v
```

Expected: 3 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/search_service.py backend/app/routers/search.py \
        backend/app/main.py backend/tests/test_search.py
git commit -m "feat: NLP search service — plain English queries translated to PostgreSQL FTS + field filters"
```

---

## Task 10: AI Chat Engine

**What you're building:** The conversational AI feature. Claude has access to everything in the workspace — entities, transactions, findings, leads, and document text — and can answer questions and surface new leads.

**Files:**
- Create: `backend/app/services/ai_engine.py`
- Create: `backend/app/schemas/ai.py`
- Create: `backend/app/routers/ai.py`
- Create: `backend/tests/test_ai.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Write failing tests — `backend/tests/test_ai.py`**

```python
import pytest
from unittest.mock import patch, MagicMock

@pytest.fixture
def workspace_id(client, auth_headers):
    return client.post("/workspaces/",
                       json={"name": "Bright Future Inc", "subject_name": "Sarah Mitchell",
                             "vertical": "fraud"},
                       headers=auth_headers).json()["id"]

def test_create_conversation(client, auth_headers, workspace_id):
    response = client.post(f"/workspaces/{workspace_id}/conversations", headers=auth_headers)
    assert response.status_code == 201
    assert response.json()["workspace_id"] == workspace_id

def test_send_message_returns_assistant_response(client, auth_headers, workspace_id):
    conv = client.post(f"/workspaces/{workspace_id}/conversations",
                       headers=auth_headers).json()

    with patch("app.services.ai_engine.Anthropic") as mock_anthropic:
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client
        mock_client.messages.create.return_value = MagicMock(
            content=[MagicMock(text="Based on the case data, I found 6 overpayment transactions.")]
        )
        response = client.post(
            f"/workspaces/{workspace_id}/conversations/{conv['id']}/messages",
            json={"content": "What overpayments are in this case?"},
            headers=auth_headers
        )

    assert response.status_code == 201
    data = response.json()
    assert data["role"] == "assistant"
    assert len(data["content"]) > 0

def test_conversation_title_set_from_first_message(client, auth_headers, workspace_id):
    conv = client.post(f"/workspaces/{workspace_id}/conversations",
                       headers=auth_headers).json()
    assert conv["title"] is None

    with patch("app.services.ai_engine.Anthropic") as mock_anthropic:
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client
        mock_client.messages.create.return_value = MagicMock(
            content=[MagicMock(text="Here is what I found.")]
        )
        client.post(
            f"/workspaces/{workspace_id}/conversations/{conv['id']}/messages",
            json={"content": "What entities are in this case?"},
            headers=auth_headers
        )

    updated = client.get(f"/workspaces/{workspace_id}/conversations",
                         headers=auth_headers).json()
    conv_updated = next(c for c in updated if c["id"] == conv["id"])
    assert conv_updated["title"] is not None
```

- [ ] **Step 2: Create `backend/app/services/ai_engine.py`**

```python
from anthropic import Anthropic
from sqlalchemy.orm import Session
from app.config import settings
from app.models.workspace import Workspace
from app.models.entity import Entity, Relationship
from app.models.transaction import Transaction
from app.models.finding import Finding
from app.models.lead import InvestigationLead
from app.models.document import Document
from app.models.document_extraction import DocumentExtraction
from app.models.ai import AIMessage

client = Anthropic(api_key=settings.anthropic_api_key)

def build_workspace_context(workspace_id: str, db: Session) -> str:
    """
    Build a complete text summary of everything in the workspace.
    This is what Claude reads before answering any question.
    The richer this context, the better Claude's answers.
    """
    workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    entities = db.query(Entity).filter(
        Entity.workspace_id == workspace_id, Entity.is_deleted == False
    ).all()
    transactions = db.query(Transaction).filter(Transaction.workspace_id == workspace_id).all()
    findings = db.query(Finding).filter(Finding.workspace_id == workspace_id).all()
    leads = db.query(InvestigationLead).filter(
        InvestigationLead.workspace_id == workspace_id
    ).all()
    docs = db.query(Document).filter(Document.workspace_id == workspace_id).all()

    lines = [
        f"WORKSPACE: {workspace.name}",
        f"Subject: {workspace.subject_name or 'Not specified'}",
        f"Jurisdiction: {workspace.jurisdiction or 'Not specified'}",
        f"Vertical: {workspace.vertical}",
        f"Status: {workspace.status}",
        "",
        f"ENTITIES ({len(entities)}):",
    ]

    for e in entities:
        lines.append(f"  [{e.type.upper()}] {e.name} — status: {e.status}")
        if e.data:
            for k, v in e.data.items():
                lines.append(f"    {k}: {v}")

    lines.append(f"\nTRANSACTIONS ({len(transactions)}):")
    for t in transactions:
        overpay = ""
        if t.amount_paid and t.appraised_value and float(t.appraised_value) > 0:
            pct = int(((float(t.amount_paid) - float(t.appraised_value)) / float(t.appraised_value)) * 100)
            overpay = f" ({'+' if pct > 0 else ''}{pct}% vs appraised)"
        lines.append(
            f"  {t.transaction_type} | paid: ${t.amount_paid} | "
            f"appraised: ${t.appraised_value}{overpay} | "
            f"date: {t.transaction_date} | instrument: {t.instrument_number}"
        )
        if t.notes:
            lines.append(f"    note: {t.notes}")

    lines.append(f"\nFINDINGS ({len(findings)}):")
    for f in findings:
        lines.append(f"  [{f.severity.upper()}] {f.title} — {f.status}")
        if f.description:
            lines.append(f"    {f.description}")

    open_leads = [l for l in leads if l.status in ("pending", "in_progress")]
    lines.append(f"\nOPEN INVESTIGATION LEADS ({len(open_leads)}):")
    for l in open_leads:
        lines.append(f"  • {l.question} (source: {l.source or 'not specified'})")

    lines.append(f"\nDOCUMENTS ({len(docs)}):")
    for doc in docs:
        lines.append(f"  {doc.filename} [{doc.detected_doc_type or 'unknown type'}]")

    return "\n".join(lines)

def get_conversation_history(conversation_id: str, db: Session, limit: int = 20) -> list[dict]:
    """Get the last N messages in a conversation, in chronological order."""
    messages = (
        db.query(AIMessage)
        .filter(AIMessage.conversation_id == conversation_id)
        .order_by(AIMessage.created_at.desc())
        .limit(limit)
        .all()
    )
    return [{"role": m.role, "content": m.content} for m in reversed(messages)]

def chat(workspace_id: str, conversation_id: str, user_message: str, db: Session) -> str:
    """
    Send a message to Claude with full workspace context.
    Returns Claude's response as a string.
    """
    workspace_context = build_workspace_context(workspace_id, db)
    history = get_conversation_history(conversation_id, db)

    system_prompt = f"""You are an investigation assistant helping analyze documents and case data. You have access to the complete workspace data below. Answer questions accurately based on this data only — do not speculate beyond what the data shows.

Be precise with numbers, dates, names, and document references. When you identify something that hasn't been investigated yet, mention it at the end as "Next lead to consider: [question]".

WORKSPACE DATA:
{workspace_context}"""

    messages = history + [{"role": "user", "content": user_message}]

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        system=system_prompt,
        messages=messages,
    )
    return response.content[0].text
```

- [ ] **Step 3: Create `backend/app/schemas/ai.py`**

```python
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class MessageCreate(BaseModel):
    content: str

class ConversationOut(BaseModel):
    id: str
    workspace_id: str
    user_id: str
    title: Optional[str]
    created_at: datetime
    class Config:
        from_attributes = True

class MessageOut(BaseModel):
    id: str
    conversation_id: str
    role: str
    content: str
    created_at: datetime
    class Config:
        from_attributes = True
```

- [ ] **Step 4: Create `backend/app/routers/ai.py`**

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.ai import AIConversation, AIMessage
from app.models.user import User
from app.schemas.ai import MessageCreate, ConversationOut, MessageOut
from app.services.auth import get_current_user
from app.services.ai_engine import chat
from app.services import audit
from app.routers.workspaces import get_workspace_or_404

router = APIRouter(prefix="/workspaces/{workspace_id}", tags=["ai"])

@router.post("/conversations", response_model=ConversationOut, status_code=201)
def create_conversation(workspace_id: str, db: Session = Depends(get_db),
                        user: User = Depends(get_current_user)):
    get_workspace_or_404(workspace_id, user, db)
    conv = AIConversation(workspace_id=workspace_id, user_id=user.id)
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return conv

@router.get("/conversations", response_model=list[ConversationOut])
def list_conversations(workspace_id: str, db: Session = Depends(get_db),
                       user: User = Depends(get_current_user)):
    get_workspace_or_404(workspace_id, user, db)
    return db.query(AIConversation).filter(
        AIConversation.workspace_id == workspace_id
    ).all()

@router.post("/conversations/{conversation_id}/messages", response_model=MessageOut, status_code=201)
def send_message(workspace_id: str, conversation_id: str, payload: MessageCreate,
                 db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    get_workspace_or_404(workspace_id, user, db)
    conv = db.query(AIConversation).filter(
        AIConversation.id == conversation_id,
        AIConversation.workspace_id == workspace_id
    ).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Store the user's message
    user_msg = AIMessage(conversation_id=conversation_id, role="user", content=payload.content)
    db.add(user_msg)
    db.commit()

    # Auto-set the conversation title from the first message
    if not conv.title:
        conv.title = payload.content[:60] + ("..." if len(payload.content) > 60 else "")
        db.commit()

    # Get Claude's response
    response_text = chat(workspace_id, conversation_id, payload.content, db)

    # Store Claude's response
    assistant_msg = AIMessage(
        conversation_id=conversation_id, role="assistant", content=response_text
    )
    db.add(assistant_msg)
    db.commit()
    db.refresh(assistant_msg)

    audit.log(db, action="queried", user_id=user.id, workspace_id=workspace_id,
              entity_type="ai_conversation", entity_id=conversation_id)
    return assistant_msg

@router.get("/conversations/{conversation_id}/messages", response_model=list[MessageOut])
def list_messages(workspace_id: str, conversation_id: str,
                  db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    get_workspace_or_404(workspace_id, user, db)
    return db.query(AIMessage).filter(
        AIMessage.conversation_id == conversation_id
    ).order_by(AIMessage.created_at).all()
```

- [ ] **Step 5: Register in `main.py`**

```python
from app.routers import (auth, workspaces, entities, findings,
                          transactions, leads, notes, documents, search, ai)
app.include_router(ai.router)
```

- [ ] **Step 6: Run tests**

```bash
pytest tests/test_ai.py -v
```

Expected: 3 tests PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/ai_engine.py backend/app/schemas/ai.py \
        backend/app/routers/ai.py backend/app/main.py backend/tests/test_ai.py
git commit -m "feat: AI chat with full workspace context, conversation history, and lead surfacing"
```

---

## Task 11: Full Verification

**What you're doing:** Running the complete test suite, then testing the live API manually to confirm everything works end-to-end inside Docker.

- [ ] **Step 1: Run the entire test suite**

```bash
cd backend
pytest tests/ -v --tb=short
```

Expected: All tests PASS. You should have approximately 30 tests.

- [ ] **Step 2: Start the full Docker environment**

```bash
docker-compose up --build
```

- [ ] **Step 3: Test the API manually with curl**

```bash
# Register a user
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"tyler@example.com","password":"Test123!","full_name":"Tyler Collins"}'

# Log in — copy the access_token from the response
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"tyler@example.com","password":"Test123!"}'

# Create a workspace (replace YOUR_TOKEN with the token from login)
curl -X POST http://localhost:8000/workspaces/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"Bright Future Ministries Inc","subject_name":"Sarah Mitchell","jurisdiction":"Madison County, OH","vertical":"fraud"}'
```

Expected: Workspace created with an ID, status "active", vertical "fraud".

- [ ] **Step 4: Verify audit log is truly immutable**

```bash
docker-compose exec db psql -U catalyst -d catalyst \
  -c "UPDATE audit_log SET action='tampered' WHERE id = (SELECT id FROM audit_log LIMIT 1);"
```

Expected:
```
ERROR:  audit_log rows are immutable — they cannot be modified or deleted
```

- [ ] **Step 5: Open the FastAPI docs and explore**

Open `http://localhost:8000/docs` in your browser. Every endpoint is listed here with interactive test forms. Try uploading a document and see the extraction results come back.

- [ ] **Step 6: Final commit**

```bash
git add .
git commit -m "feat: Phase 1 backend API complete — all tests passing, audit log immutability verified"
```

---

## What Comes Next

1. **Frontend plan** (`2026-05-17-phase1-frontend.md`) — The React app that consumes this API. 8 workspace sections, NLP search bar, document upload UI, AI chat interface.

2. **Document type sub-spec** — Before Phase 2, write the dedicated spec defining every document type (Form 990, UCC, deed, SOS filing, building permit) with exact AI extraction field schemas. The TEOS XML format for 990s is confirmed as the preferred source.

3. **Seed document schemas** — The `document_schemas` table needs seed data defining extraction templates for DEED, 990, UCC, SOS-FILING, BUILDING-PERMIT, and INSURANCE-FORM. This is added in Phase 2 after the document type sub-spec is written.
