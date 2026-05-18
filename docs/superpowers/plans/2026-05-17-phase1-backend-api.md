# Phase 1 Backend API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Phase 1 backend API — an Intelligent Document Processing engine with deep extraction, NLP search, workspace management, AI chat, and evidence integrity. The fraud investigation vertical (findings, signals, leads) is built on top of this IDP core.

**Architecture:** FastAPI backend with SQLAlchemy 2.0 ORM. Routers are thin — they validate input, call a service, return a response. All business logic lives in service classes. The document pipeline runs synchronously. The audit log is append-only, enforced at the PostgreSQL database level (not just in code).

**Tech Stack:** Python 3.12, FastAPI 0.115, SQLAlchemy 2.0, Alembic 1.13, PostgreSQL 16, PyMuPDF, pytesseract, Anthropic SDK, pytest, httpx

**Written for:** A junior developer who just finished their IBM full stack cert. Every decision in this plan has a reason. Read the WHY notes — they explain things your future self will thank you for knowing.

**Companion plan:** `2026-05-17-phase1-frontend.md` — build the React frontend after this plan is complete and all tests pass.

---

## How This Plan Works

Each task builds on the previous one. Tasks follow Test-Driven Development (TDD):
1. Write the test first (it will fail — that's expected)
2. Run it to confirm it fails
3. Write the minimum code to make it pass
4. Run it again to confirm it passes
5. Commit

**Why TDD?** When you write the test first, you're forced to think about what the code should DO before thinking about how to build it. It also gives you a safety net — if you break something later, your tests will catch it immediately.

---

## File Map

```
backend/
├── app/
│   ├── main.py                      # FastAPI app setup, routers registered here
│   ├── config.py                    # All settings loaded from environment variables
│   ├── database.py                  # Database connection and session management
│   ├── models/
│   │   ├── __init__.py              # Imports all models (Alembic needs this)
│   │   ├── user.py                  # User table
│   │   ├── workspace.py             # Workspace + WorkspaceMember tables
│   │   ├── entity.py                # Entity + Relationship tables
│   │   ├── document.py              # Document table
│   │   ├── document_schema.py       # DocumentSchema table (extraction templates)
│   │   ├── document_extraction.py   # DocumentExtraction table (key IDP table)
│   │   ├── transaction.py           # Transaction table
│   │   ├── finding.py               # SignalType + Finding + FindingEvidence tables
│   │   ├── lead.py                  # InvestigationLead table
│   │   ├── note.py                  # Note table
│   │   ├── ai.py                    # AIConversation + AIMessage tables
│   │   └── audit.py                 # AuditLog table
│   ├── schemas/
│   │   ├── user.py                  # Pydantic models for user endpoints
│   │   ├── workspace.py             # Pydantic models for workspace endpoints
│   │   ├── entity.py                # Pydantic models for entity endpoints
│   │   ├── document.py              # Pydantic models for document endpoints
│   │   ├── transaction.py           # Pydantic models for transaction endpoints
│   │   ├── finding.py               # Pydantic models for finding endpoints
│   │   ├── lead.py                  # Pydantic models for lead endpoints
│   │   ├── note.py                  # Pydantic models for note endpoints
│   │   └── ai.py                    # Pydantic models for AI chat endpoints
│   ├── routers/
│   │   ├── auth.py                  # POST /auth/register, POST /auth/login
│   │   ├── workspaces.py            # CRUD /workspaces and /workspaces/{id}/members
│   │   ├── entities.py              # CRUD /workspaces/{id}/entities and /relationships
│   │   ├── documents.py             # POST /workspaces/{id}/documents, GET list/detail
│   │   ├── transactions.py          # CRUD /workspaces/{id}/transactions
│   │   ├── findings.py              # CRUD /workspaces/{id}/findings, GET /signal-types
│   │   ├── leads.py                 # CRUD /workspaces/{id}/leads
│   │   ├── notes.py                 # CRUD /workspaces/{id}/notes
│   │   ├── search.py                # POST /workspaces/{id}/search (NLP search)
│   │   └── ai.py                    # POST /workspaces/{id}/conversations + messages
│   ├── services/
│   │   ├── auth.py                  # JWT creation/verification, password hashing
│   │   ├── document_pipeline.py     # Orchestrates: hash → store → OCR → extract → index
│   │   ├── ocr.py                   # Text extraction from PDFs and images
│   │   ├── extraction_engine.py     # Schema detection + AI field extraction
│   │   ├── naming.py                # AI-powered standardized filename generation
│   │   ├── search_service.py        # NLP query → SQL/FTS → results
│   │   ├── ai_engine.py             # Claude chat with full workspace context
│   │   └── audit.py                 # Writes rows to the audit_log table
│   └── middleware/
│       └── audit_middleware.py      # Auto-logs every HTTP request
├── alembic/
│   ├── env.py                       # Alembic configuration (auto-generated + modified)
│   └── versions/
│       └── 001_initial_schema.py    # The migration that creates all tables
├── tests/
│   ├── conftest.py                  # Shared test fixtures (test DB, test client, auth)
│   ├── test_auth.py
│   ├── test_workspaces.py
│   ├── test_entities.py
│   ├── test_documents.py
│   ├── test_extractions.py
│   ├── test_search.py
│   ├── test_transactions.py
│   ├── test_findings.py
│   ├── test_leads.py
│   ├── test_notes.py
│   └── test_ai.py
├── uploads/                         # Local file storage during development (gitignored)
├── requirements.txt
├── Dockerfile
└── .env.example
docker-compose.yml                   # At the project root, not inside backend/
```

---

## Task 1: Project Scaffold + Docker

**What you're building:** The empty skeleton of the project — folder structure, Docker configuration, and a single working endpoint to prove the system is running. Everything else builds on this.

**Why Docker from day one?** Docker packages your app and all its dependencies so it runs identically on your laptop and on AWS. Without Docker, "it works on my machine" is a real problem. With Docker, your machine IS the server.

**Files:**
- Create: `docker-compose.yml` (project root)
- Create: `backend/requirements.txt`
- Create: `backend/Dockerfile`
- Create: `backend/.env.example`
- Create: `backend/app/config.py`
- Create: `backend/app/database.py`
- Create: `backend/app/main.py`

- [ ] **Step 1: Create the directory structure**

```bash
mkdir -p backend/app/models backend/app/schemas backend/app/routers \
         backend/app/services backend/app/middleware \
         backend/alembic/versions backend/tests backend/uploads

touch backend/app/__init__.py
touch backend/app/models/__init__.py
touch backend/app/schemas/__init__.py
touch backend/app/routers/__init__.py
touch backend/app/services/__init__.py
touch backend/app/middleware/__init__.py
touch backend/tests/__init__.py
```

- [ ] **Step 2: Create `docker-compose.yml` at the project root**

```yaml
version: "3.9"

services:
  db:
    image: postgres:16
    environment:
      POSTGRES_USER: catalyst
      POSTGRES_PASSWORD: catalyst
      POSTGRES_DB: catalyst
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data

  backend:
    build: ./backend
    ports:
      - "8000:8000"
    environment:
      DATABASE_URL: postgresql://catalyst:catalyst@db:5432/catalyst
      SECRET_KEY: dev-secret-key-change-in-production
      ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY}
      UPLOAD_DIR: /app/uploads
    volumes:
      - ./backend:/app
      - uploads_data:/app/uploads
    depends_on:
      - db
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

volumes:
  postgres_data:
  uploads_data:
```

- [ ] **Step 3: Create `backend/requirements.txt`**

```
fastapi==0.115.0
uvicorn[standard]==0.30.6
sqlalchemy==2.0.31
alembic==1.13.2
psycopg2-binary==2.9.9
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
python-multipart==0.0.9
PyMuPDF==1.24.9
pytesseract==0.3.13
Pillow==10.4.0
anthropic==0.34.2
pydantic-settings==2.4.0
python-dotenv==1.0.1
pytest==8.3.2
pytest-asyncio==0.23.8
httpx==0.27.2
```

- [ ] **Step 4: Create `backend/Dockerfile`**

```dockerfile
FROM python:3.12-slim

# Install tesseract (OCR engine) and libgl1 (needed by PyMuPDF)
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    libgl1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 5: Create `backend/.env.example`**

```
DATABASE_URL=postgresql://catalyst:catalyst@localhost:5432/catalyst
SECRET_KEY=change-this-to-a-long-random-string-in-production
ANTHROPIC_API_KEY=sk-ant-your-key-here
UPLOAD_DIR=./uploads
```

- [ ] **Step 6: Create `backend/app/config.py`**

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # These values are loaded from environment variables automatically.
    # pydantic-settings reads your .env file and matches variable names.
    database_url: str
    secret_key: str
    anthropic_api_key: str
    upload_dir: str = "./uploads"
    access_token_expire_minutes: int = 60 * 24  # 24 hours

    class Config:
        env_file = ".env"

# Create one instance that the whole app imports and uses.
# This is the "singleton" pattern — one settings object, used everywhere.
settings = Settings()
```

- [ ] **Step 7: Create `backend/app/database.py`**

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from app.config import settings

# The engine is the connection to the database.
engine = create_engine(settings.database_url)

# SessionLocal creates database sessions. Each request gets its own session.
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base is the parent class all our models will inherit from.
# SQLAlchemy uses it to know which classes map to database tables.
class Base(DeclarativeBase):
    pass

def get_db():
    """
    FastAPI dependency that provides a database session per request.
    The 'yield' makes this a generator — code after yield runs on cleanup.
    The session is always closed when the request ends, even if it fails.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

- [ ] **Step 8: Create `backend/app/main.py`**

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="Verity Prism IDP Platform",
    description="Intelligent Document Processing Platform",
    version="1.0.0"
)

# CORS tells the browser it's OK for the frontend (localhost:5173)
# to make requests to this backend (localhost:8000).
# Without this, the browser blocks all cross-origin requests.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health():
    return {"status": "ok"}
```

- [ ] **Step 9: Start Docker and verify it works**

```bash
cd backend
cp .env.example .env
# Open .env and add your real ANTHROPIC_API_KEY
docker-compose up --build
```

Open a second terminal and run:
```bash
curl http://localhost:8000/health
```

Expected output: `{"status":"ok"}`

Also open `http://localhost:8000/docs` in your browser. FastAPI generates interactive API documentation automatically — you'll use this constantly while building.

- [ ] **Step 10: Commit**

```bash
git add docker-compose.yml backend/
git commit -m "feat: project scaffold with FastAPI, PostgreSQL, and Docker"
```

---

## Task 2: All Database Models + Migration

**What you're building:** Every table in the database, defined as Python classes. SQLAlchemy reads these classes and knows how to create and query the tables.

**What is a migration?** A migration is a script that changes the database structure. Alembic (a migration tool for Python) tracks which migrations have run. When you add a new table or column, you create a new migration — Alembic applies it to the database without losing existing data.

**Why define models before writing any API code?** The database is the foundation. If the foundation is wrong, everything built on it needs to change. Get the tables right first.

**Files:** Create all files in `backend/app/models/`

- [ ] **Step 1: Create `backend/app/models/user.py`**

```python
import uuid
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base

class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid.uuid4())
    )
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    full_name: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[str] = mapped_column(
        SAEnum("owner", "member", name="user_role"), default="member"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
```

- [ ] **Step 2: Create `backend/app/models/workspace.py`**

```python
import uuid
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, Enum as SAEnum, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base

class Workspace(Base):
    __tablename__ = "workspaces"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=True)
    subject_name: Mapped[str] = mapped_column(String, nullable=True)
    jurisdiction: Mapped[str] = mapped_column(String, nullable=True)
    vertical: Mapped[str] = mapped_column(
        SAEnum("fraud", "insurance", "general", name="workspace_vertical"), default="general"
    )
    status: Mapped[str] = mapped_column(
        SAEnum("active", "closed", "archived", name="workspace_status"), default="active"
    )
    created_by: Mapped[str] = mapped_column(String, ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )

class WorkspaceMember(Base):
    __tablename__ = "workspace_members"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id: Mapped[str] = mapped_column(String, ForeignKey("workspaces.id"), nullable=False)
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"), nullable=False)
    role: Mapped[str] = mapped_column(
        SAEnum("owner", "analyst", "viewer", name="member_role"), default="analyst"
    )
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
```

- [ ] **Step 3: Create `backend/app/models/document_schema.py`**

```python
import uuid
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, Integer, Boolean, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base

class DocumentSchema(Base):
    """
    Defines what fields Claude should extract from each document type.
    Think of this as the instruction manual for the AI extraction engine.
    One schema per document type (DEED, 990, UCC, INSURANCE-FORM, etc.)
    """
    __tablename__ = "document_schemas"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    document_type: Mapped[str] = mapped_column(String, nullable=False)
    vertical: Mapped[str] = mapped_column(String, default="general")
    display_name: Mapped[str] = mapped_column(String, nullable=False)
    # schema_fields is a JSON list like:
    # [{"name": "grantor_name", "type": "name", "description": "...", "required": true}]
    schema_fields: Mapped[list] = mapped_column(JSONB, default=list)
    extraction_prompt: Mapped[str] = mapped_column(Text, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
```

- [ ] **Step 4: Create `backend/app/models/document.py`**

```python
import uuid
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, Enum as SAEnum, ForeignKey, Text, BigInteger
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import Index
from app.database import Base

class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id: Mapped[str] = mapped_column(String, ForeignKey("workspaces.id"), nullable=False)
    filename: Mapped[str] = mapped_column(String, nullable=False)
    original_filename: Mapped[str] = mapped_column(String, nullable=False)
    file_path: Mapped[str] = mapped_column(String, nullable=False)
    file_type: Mapped[str] = mapped_column(
        SAEnum("pdf", "image", "csv", "text", "xml", "other", name="file_type"), nullable=False
    )
    # SHA-256 hash — the evidence fingerprint. Generated before anything else.
    sha256_hash: Mapped[str] = mapped_column(String, nullable=False)
    source_url: Mapped[str] = mapped_column(String, nullable=True)
    source_type: Mapped[str] = mapped_column(
        SAEnum("upload", "api_pull", "manual_entry", name="source_type"), default="upload"
    )
    detected_doc_type: Mapped[str] = mapped_column(String, nullable=True)
    schema_id: Mapped[str] = mapped_column(String, ForeignKey("document_schemas.id"), nullable=True)
    ocr_text: Mapped[str] = mapped_column(Text, nullable=True)
    # search_vector is a special PostgreSQL type for full-text search.
    # We store it as Text here and let a trigger keep it updated.
    # The GIN index below makes searches fast.
    search_vector: Mapped[str] = mapped_column(Text, nullable=True)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=True)
    extraction_status: Mapped[str] = mapped_column(
        SAEnum("pending", "complete", "failed", name="extraction_status"), default="pending"
    )
    uploaded_by: Mapped[str] = mapped_column(String, ForeignKey("users.id"), nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
```

- [ ] **Step 5: Create `backend/app/models/document_extraction.py`**

```python
import uuid
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, Enum as SAEnum, ForeignKey, Float
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base

class DocumentExtraction(Base):
    """
    The key IDP table. One row per extracted field per document.
    A deed with 11 fields = 11 rows here.
    A Form 990 with 60 fields = 60 rows here.
    Every single field is individually searchable.
    """
    __tablename__ = "document_extractions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    document_id: Mapped[str] = mapped_column(String, ForeignKey("documents.id"), nullable=False)
    # workspace_id is stored here too (denormalized) so searches across a workspace
    # don't need to join through the documents table. This is a performance optimization.
    workspace_id: Mapped[str] = mapped_column(String, ForeignKey("workspaces.id"), nullable=False)
    field_name: Mapped[str] = mapped_column(String, nullable=False)
    field_value: Mapped[str] = mapped_column(String, nullable=True)
    field_type: Mapped[str] = mapped_column(
        SAEnum("name", "date", "currency", "address", "id_number", "text", "boolean",
               name="extraction_field_type"),
        default="text"
    )
    # confidence: how sure Claude is. 0.0 = no idea. 1.0 = certain.
    # We surface low-confidence extractions (< 0.7) for manual review.
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    schema_id: Mapped[str] = mapped_column(String, ForeignKey("document_schemas.id"), nullable=True)
    extracted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
```

- [ ] **Step 6: Create `backend/app/models/entity.py`**

```python
import uuid
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, Enum as SAEnum, ForeignKey, Boolean, Date
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base

class Entity(Base):
    __tablename__ = "entities"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id: Mapped[str] = mapped_column(String, ForeignKey("workspaces.id"), nullable=False)
    type: Mapped[str] = mapped_column(
        SAEnum("person", "organization", "property", "financial_account", name="entity_type"),
        nullable=False
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(
        SAEnum("active", "dissolved", "deceased", "unknown", name="entity_status"), default="active"
    )
    # data holds type-specific details as flexible JSON:
    # person: {"dob": "1975-03-12", "address": "6172 Olding Rd"}
    # organization: {"ein": "82-4458479", "sos_id": "4128601"}
    # property: {"parcel_number": "M51-2-312-12-01-01-12300", "appraised_value": 37490}
    data: Mapped[dict] = mapped_column(JSONB, default=dict)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    deleted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[str] = mapped_column(String, ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class Relationship(Base):
    __tablename__ = "relationships"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id: Mapped[str] = mapped_column(String, ForeignKey("workspaces.id"), nullable=False)
    entity_a_id: Mapped[str] = mapped_column(String, ForeignKey("entities.id"), nullable=False)
    entity_b_id: Mapped[str] = mapped_column(String, ForeignKey("entities.id"), nullable=False)
    type: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=True)
    start_date: Mapped[datetime] = mapped_column(Date, nullable=True)
    end_date: Mapped[datetime] = mapped_column(Date, nullable=True)
    source_doc_id: Mapped[str] = mapped_column(String, ForeignKey("documents.id"), nullable=True)
    created_by: Mapped[str] = mapped_column(String, ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
```

- [ ] **Step 7: Create `backend/app/models/transaction.py`**

```python
import uuid
from datetime import datetime, timezone, date
from sqlalchemy import String, DateTime, Enum as SAEnum, ForeignKey, Numeric, Date
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base

class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id: Mapped[str] = mapped_column(String, ForeignKey("workspaces.id"), nullable=False)
    entity_from_id: Mapped[str] = mapped_column(String, ForeignKey("entities.id"), nullable=True)
    entity_to_id: Mapped[str] = mapped_column(String, ForeignKey("entities.id"), nullable=True)
    transaction_type: Mapped[str] = mapped_column(
        SAEnum("purchase", "transfer", "lien", "loan", "donation", "construction", "compensation",
               name="transaction_type"), nullable=False
    )
    amount_paid: Mapped[float] = mapped_column(Numeric(15, 2), nullable=True)
    appraised_value: Mapped[float] = mapped_column(Numeric(15, 2), nullable=True)
    consideration: Mapped[str] = mapped_column(
        SAEnum("zero", "below_market", "fair_market", "above_market", name="consideration_type"),
        nullable=True
    )
    transaction_date: Mapped[date] = mapped_column(Date, nullable=True)
    recorded_date: Mapped[date] = mapped_column(Date, nullable=True)
    instrument_number: Mapped[str] = mapped_column(String, nullable=True)
    source_doc_id: Mapped[str] = mapped_column(String, ForeignKey("documents.id"), nullable=True)
    notes: Mapped[str] = mapped_column(String, nullable=True)
    created_by: Mapped[str] = mapped_column(String, ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
```

- [ ] **Step 8: Create `backend/app/models/finding.py`**

```python
import uuid
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, Enum as SAEnum, ForeignKey, ARRAY
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base

class SignalType(Base):
    __tablename__ = "signal_types"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    code: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=False)
    severity: Mapped[str] = mapped_column(
        SAEnum("critical", "high", "medium", "low", name="signal_severity"), nullable=False
    )
    relevant_to: Mapped[list] = mapped_column(ARRAY(String), default=list)

class Finding(Base):
    __tablename__ = "findings"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id: Mapped[str] = mapped_column(String, ForeignKey("workspaces.id"), nullable=False)
    signal_type_id: Mapped[str] = mapped_column(String, ForeignKey("signal_types.id"), nullable=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=True)
    severity: Mapped[str] = mapped_column(
        SAEnum("critical", "high", "medium", "low", name="finding_severity"), nullable=False
    )
    status: Mapped[str] = mapped_column(
        SAEnum("open", "confirmed", "dismissed", name="finding_status"), default="open"
    )
    created_by: Mapped[str] = mapped_column(String, ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class FindingEvidence(Base):
    __tablename__ = "finding_evidence"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    finding_id: Mapped[str] = mapped_column(String, ForeignKey("findings.id"), nullable=False)
    document_id: Mapped[str] = mapped_column(String, ForeignKey("documents.id"), nullable=True)
    entity_id: Mapped[str] = mapped_column(String, ForeignKey("entities.id"), nullable=True)
    note: Mapped[str] = mapped_column(String, nullable=True)
    added_by: Mapped[str] = mapped_column(String, ForeignKey("users.id"), nullable=False)
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
```

- [ ] **Step 9: Create `backend/app/models/lead.py`**

```python
import uuid
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, Enum as SAEnum, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base

class InvestigationLead(Base):
    __tablename__ = "investigation_leads"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id: Mapped[str] = mapped_column(String, ForeignKey("workspaces.id"), nullable=False)
    question: Mapped[str] = mapped_column(String, nullable=False)
    source: Mapped[str] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(
        SAEnum("pending", "in_progress", "complete", "dead_end", name="lead_status"), default="pending"
    )
    originated_by: Mapped[str] = mapped_column(
        SAEnum("user", "ai", "external_tip", name="lead_origin"), default="user"
    )
    triggered_by_id: Mapped[str] = mapped_column(
        String, ForeignKey("investigation_leads.id"), nullable=True
    )
    assigned_to: Mapped[str] = mapped_column(String, ForeignKey("users.id"), nullable=True)
    result_summary: Mapped[str] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
```

- [ ] **Step 10: Create `backend/app/models/note.py`**

```python
import uuid
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, Enum as SAEnum, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base

class Note(Base):
    __tablename__ = "notes"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id: Mapped[str] = mapped_column(String, ForeignKey("workspaces.id"), nullable=False)
    author_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"), nullable=False)
    entity_type: Mapped[str] = mapped_column(
        SAEnum("workspace", "entity", "document", "finding", "transaction", "lead",
               name="note_entity_type"), nullable=False
    )
    entity_id: Mapped[str] = mapped_column(String, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
```

- [ ] **Step 11: Create `backend/app/models/ai.py`**

```python
import uuid
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, Enum as SAEnum, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base

class AIConversation(Base):
    __tablename__ = "ai_conversations"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id: Mapped[str] = mapped_column(String, ForeignKey("workspaces.id"), nullable=False)
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"), nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class AIMessage(Base):
    __tablename__ = "ai_messages"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    conversation_id: Mapped[str] = mapped_column(String, ForeignKey("ai_conversations.id"), nullable=False)
    role: Mapped[str] = mapped_column(SAEnum("user", "assistant", name="message_role"), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
```

- [ ] **Step 12: Create `backend/app/models/audit.py`**

```python
import uuid
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base

class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id: Mapped[str] = mapped_column(String, ForeignKey("workspaces.id"), nullable=True)
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String, nullable=False)
    entity_type: Mapped[str] = mapped_column(String, nullable=True)
    entity_id: Mapped[str] = mapped_column(String, nullable=True)
    before_state: Mapped[dict] = mapped_column(JSONB, nullable=True)
    after_state: Mapped[dict] = mapped_column(JSONB, nullable=True)
    ip_address: Mapped[str] = mapped_column(String, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
```

- [ ] **Step 13: Create `backend/app/models/__init__.py`**

```python
# This file imports every model so Alembic can find them when generating migrations.
# If you add a new model file, import it here.
from app.models.user import User
from app.models.workspace import Workspace, WorkspaceMember
from app.models.document_schema import DocumentSchema
from app.models.document import Document
from app.models.document_extraction import DocumentExtraction
from app.models.entity import Entity, Relationship
from app.models.transaction import Transaction
from app.models.finding import SignalType, Finding, FindingEvidence
from app.models.lead import InvestigationLead
from app.models.note import Note
from app.models.ai import AIConversation, AIMessage
from app.models.audit import AuditLog

__all__ = [
    "User", "Workspace", "WorkspaceMember",
    "DocumentSchema", "Document", "DocumentExtraction",
    "Entity", "Relationship", "Transaction",
    "SignalType", "Finding", "FindingEvidence",
    "InvestigationLead", "Note",
    "AIConversation", "AIMessage", "AuditLog",
]
```

- [ ] **Step 14: Initialize Alembic**

```bash
cd backend
alembic init alembic
```

This creates the `alembic/` directory and a config file.

- [ ] **Step 15: Replace `backend/alembic/env.py`**

```python
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context
import app.models  # noqa — this import makes Alembic see all our models
from app.config import settings
from app.database import Base

config = context.config
config.set_main_option("sqlalchemy.url", settings.database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

def run_migrations_online():
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()

run_migrations_online()
```

- [ ] **Step 16: Generate and run the migration**

```bash
cd backend
alembic revision --autogenerate -m "initial schema"
alembic upgrade head
```

Expected: A file appears in `alembic/versions/` starting with a hash and ending in `_initial_schema.py`. The `upgrade head` command runs it and creates all tables in PostgreSQL.

- [ ] **Step 17: Set up the FTS index and audit log protection**

Connect to PostgreSQL and run these SQL commands:

```bash
docker-compose exec db psql -U catalyst -d catalyst
```

Then paste this SQL:

```sql
-- Full-text search: convert the search_vector column to a proper tsvector type.
-- tsvector is PostgreSQL's optimized format for full-text search.
-- The GIN index makes searches fast even across millions of words.
ALTER TABLE documents ALTER COLUMN search_vector TYPE tsvector USING search_vector::tsvector;
CREATE INDEX idx_documents_search_vector ON documents USING GIN(search_vector);

-- Add indexes on document_extractions for fast field-level queries.
-- These let us answer: "find all grantor_names in workspace X" instantly.
CREATE INDEX idx_extractions_workspace_field ON document_extractions(workspace_id, field_name);
CREATE INDEX idx_extractions_document_field ON document_extractions(document_id, field_name);

-- Audit log protection: a database trigger prevents anyone from
-- updating or deleting rows in audit_log — even if they have full DB access.
CREATE OR REPLACE FUNCTION prevent_audit_log_modification()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'audit_log rows are immutable — they cannot be modified or deleted';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER audit_log_immutable
BEFORE UPDATE OR DELETE ON audit_log
FOR EACH ROW EXECUTE FUNCTION prevent_audit_log_modification();
```

Type `\q` to exit psql.

- [ ] **Step 18: Commit**

```bash
git add backend/app/models/ backend/alembic/
git commit -m "feat: all database models, initial migration, FTS indexes, audit log trigger"
```

---

## Task 3: Auth Service + Router

**What you're building:** User registration, login, and the JWT token system. Every protected endpoint after this uses the `get_current_user` dependency you build here.

**Files:**
- Create: `backend/app/services/auth.py`
- Create: `backend/app/services/audit.py`
- Create: `backend/app/schemas/user.py`
- Create: `backend/app/routers/auth.py`
- Create: `backend/tests/conftest.py`
- Create: `backend/tests/test_auth.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Create `backend/app/services/audit.py`**

```python
from sqlalchemy.orm import Session
from app.models.audit import AuditLog

def log(
    db: Session,
    action: str,
    user_id: str = None,
    workspace_id: str = None,
    entity_type: str = None,
    entity_id: str = None,
    before_state: dict = None,
    after_state: dict = None,
    ip_address: str = None,
):
    """
    Write one row to the audit log. Call this every time something important happens.
    The row can never be updated or deleted (enforced by the database trigger in Task 2).
    """
    entry = AuditLog(
        action=action,
        user_id=user_id,
        workspace_id=workspace_id,
        entity_type=entity_type,
        entity_id=entity_id,
        before_state=before_state,
        after_state=after_state,
        ip_address=ip_address,
    )
    db.add(entry)
    db.commit()
```

- [ ] **Step 2: Write failing tests — create `backend/tests/conftest.py`**

```python
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.main import app
from app.database import Base, get_db

# Use a separate test database so tests never touch real data
TEST_DATABASE_URL = "postgresql://catalyst:catalyst@localhost:5432/catalyst_test"

engine = create_engine(TEST_DATABASE_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(autouse=True)
def setup_db():
    """Create all tables before each test, drop them after. Every test starts clean."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

@pytest.fixture
def db():
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()

@pytest.fixture
def client(db):
    """A test HTTP client that uses the test database instead of the real one."""
    def override_get_db():
        try:
            yield db
        finally:
            pass
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()

@pytest.fixture
def registered_user(client):
    """Register a test user and return their credentials."""
    client.post("/auth/register", json={
        "email": "tyler@example.com",
        "password": "TestPass123!",
        "full_name": "Tyler Collins"
    })
    return {"email": "tyler@example.com", "password": "TestPass123!"}

@pytest.fixture
def auth_headers(client, registered_user):
    """Log in and return Authorization headers ready to use in requests."""
    response = client.post("/auth/login", json=registered_user)
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
```

- [ ] **Step 3: Create `backend/tests/test_auth.py`**

```python
def test_register_creates_user(client):
    response = client.post("/auth/register", json={
        "email": "test@example.com",
        "password": "TestPass123!",
        "full_name": "Test User"
    })
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "test@example.com"
    assert "password" not in data  # Never return the password

def test_register_duplicate_email_returns_400(client):
    payload = {"email": "dup@example.com", "password": "TestPass123!", "full_name": "User"}
    client.post("/auth/register", json=payload)
    response = client.post("/auth/register", json=payload)
    assert response.status_code == 400

def test_login_returns_jwt_token(client, registered_user):
    response = client.post("/auth/login", json=registered_user)
    assert response.status_code == 200
    assert "access_token" in response.json()

def test_wrong_password_returns_401(client, registered_user):
    response = client.post("/auth/login", json={
        "email": registered_user["email"],
        "password": "wrongpassword"
    })
    assert response.status_code == 401

def test_protected_route_without_token_returns_401(client):
    response = client.get("/workspaces/")
    assert response.status_code == 401
```

- [ ] **Step 4: Run tests to confirm they fail**

```bash
cd backend
pytest tests/test_auth.py -v
```

Expected: All tests fail with `404` or `ImportError` — the routes don't exist yet. This is correct.

- [ ] **Step 5: Create `backend/app/schemas/user.py`**

```python
from pydantic import BaseModel, EmailStr
from datetime import datetime

class UserRegister(BaseModel):
    email: EmailStr  # EmailStr validates that the string is a valid email format
    password: str
    full_name: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserOut(BaseModel):
    id: str
    email: str
    full_name: str
    role: str
    created_at: datetime

    class Config:
        from_attributes = True  # Allows converting SQLAlchemy model → Pydantic model

class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
```

- [ ] **Step 6: Create `backend/app/services/auth.py`**

```python
from datetime import datetime, timedelta, timezone
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.config import settings
from app.models.user import User
from app.database import get_db

# CryptContext handles password hashing with bcrypt
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# HTTPBearer reads the "Authorization: Bearer <token>" header from requests
bearer_scheme = HTTPBearer()

def hash_password(password: str) -> str:
    """Turn a plain password into a one-way hash. Never store plain passwords."""
    return pwd_context.hash(password)

def verify_password(plain: str, hashed: str) -> bool:
    """Check if a plain password matches a stored hash."""
    return pwd_context.verify(plain, hashed)

def create_access_token(user_id: str) -> str:
    """Create a signed JWT token that proves who the user is."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {"sub": user_id, "exp": expire}
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """
    FastAPI dependency — call this to protect any endpoint.
    Reads the JWT token from the request header, verifies it,
    and returns the User object. Raises 401 if anything is wrong.
    """
    try:
        payload = jwt.decode(credentials.credentials, settings.secret_key, algorithms=["HS256"])
        user_id: str = payload.get("sub")
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user
```

- [ ] **Step 7: Create `backend/app/routers/auth.py`**

```python
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User
from app.schemas.user import UserRegister, UserLogin, UserOut, TokenOut
from app.services.auth import hash_password, verify_password, create_access_token

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/register", response_model=UserOut, status_code=201)
def register(payload: UserRegister, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    user = User(
        email=payload.email,
        password_hash=hash_password(payload.password),
        full_name=payload.full_name,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

@router.post("/login", response_model=TokenOut)
def login(payload: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return {"access_token": create_access_token(user.id)}
```

- [ ] **Step 8: Update `backend/app/main.py`**

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import auth

app = FastAPI(title="Verity Prism", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)

@app.get("/health")
def health():
    return {"status": "ok"}
```

- [ ] **Step 9: Run tests — all should pass**

```bash
pytest tests/test_auth.py -v
```

Expected: 5 tests PASS.

- [ ] **Step 10: Commit**

```bash
git add backend/app/services/ backend/app/schemas/user.py \
        backend/app/routers/auth.py backend/app/main.py \
        backend/tests/
git commit -m "feat: auth with JWT registration, login, and protected route dependency"
```

---

## Task 4: Workspaces API

**What you're building:** The CRUD endpoints for workspaces — create, list, read, update. Access control is built in: you can only see workspaces you're a member of.

**Files:**
- Create: `backend/app/schemas/workspace.py`
- Create: `backend/app/routers/workspaces.py`
- Create: `backend/tests/test_workspaces.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Write failing tests — `backend/tests/test_workspaces.py`**

```python
import pytest

def test_create_workspace(client, auth_headers):
    response = client.post("/workspaces/", json={
        "name": "Do Good In His Name Inc",
        "subject_name": "Karen Homan",
        "jurisdiction": "Darke County, OH",
        "vertical": "fraud"
    }, headers=auth_headers)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Do Good In His Name Inc"
    assert data["status"] == "active"
    assert data["vertical"] == "fraud"

def test_list_workspaces_only_shows_own(client, auth_headers):
    client.post("/workspaces/", json={"name": "My Workspace"}, headers=auth_headers)
    response = client.get("/workspaces/", headers=auth_headers)
    assert response.status_code == 200
    assert len(response.json()) == 1

def test_get_workspace_by_id(client, auth_headers):
    created = client.post("/workspaces/", json={"name": "Test"}, headers=auth_headers).json()
    response = client.get(f"/workspaces/{created['id']}", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["id"] == created["id"]

def test_update_workspace_name(client, auth_headers):
    created = client.post("/workspaces/", json={"name": "Old Name"}, headers=auth_headers).json()
    response = client.patch(f"/workspaces/{created['id']}", json={"name": "New Name"}, headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["name"] == "New Name"

def test_cannot_access_workspace_without_token(client):
    response = client.get("/workspaces/")
    assert response.status_code == 401
```

- [ ] **Step 2: Run to confirm they fail**

```bash
pytest tests/test_workspaces.py -v
```

- [ ] **Step 3: Create `backend/app/schemas/workspace.py`**

```python
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class WorkspaceCreate(BaseModel):
    name: str
    description: Optional[str] = None
    subject_name: Optional[str] = None
    jurisdiction: Optional[str] = None
    vertical: str = "general"

class WorkspaceUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    subject_name: Optional[str] = None
    jurisdiction: Optional[str] = None
    status: Optional[str] = None

class WorkspaceOut(BaseModel):
    id: str
    name: str
    description: Optional[str]
    subject_name: Optional[str]
    jurisdiction: Optional[str]
    vertical: str
    status: str
    created_by: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
```

- [ ] **Step 4: Create `backend/app/routers/workspaces.py`**

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.workspace import Workspace, WorkspaceMember
from app.models.user import User
from app.schemas.workspace import WorkspaceCreate, WorkspaceUpdate, WorkspaceOut
from app.services.auth import get_current_user
from app.services import audit

router = APIRouter(prefix="/workspaces", tags=["workspaces"])

def get_workspace_or_404(workspace_id: str, user: User, db: Session) -> Workspace:
    """
    Verify the user has access to this workspace.
    If they're not a member, return 404 (not 403) — we don't reveal that the workspace exists.
    """
    membership = db.query(WorkspaceMember).filter(
        WorkspaceMember.workspace_id == workspace_id,
        WorkspaceMember.user_id == user.id
    ).first()
    if not membership:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return db.query(Workspace).filter(Workspace.id == workspace_id).first()

@router.post("/", response_model=WorkspaceOut, status_code=201)
def create_workspace(
    payload: WorkspaceCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    workspace = Workspace(**payload.model_dump(), created_by=user.id)
    db.add(workspace)
    db.flush()  # flush gives us the workspace.id without committing yet
    # Add the creator as the owner automatically
    member = WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role="owner")
    db.add(member)
    db.commit()
    db.refresh(workspace)
    audit.log(db, action="created", user_id=user.id, workspace_id=workspace.id,
              entity_type="workspace", entity_id=workspace.id,
              after_state={"name": workspace.name, "vertical": workspace.vertical})
    return workspace

@router.get("/", response_model=list[WorkspaceOut])
def list_workspaces(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    member_ids = [m.workspace_id for m in
                  db.query(WorkspaceMember).filter(WorkspaceMember.user_id == user.id).all()]
    return db.query(Workspace).filter(Workspace.id.in_(member_ids)).all()

@router.get("/{workspace_id}", response_model=WorkspaceOut)
def get_workspace(workspace_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return get_workspace_or_404(workspace_id, user, db)

@router.patch("/{workspace_id}", response_model=WorkspaceOut)
def update_workspace(
    workspace_id: str,
    payload: WorkspaceUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    workspace = get_workspace_or_404(workspace_id, user, db)
    before = {"name": workspace.name, "status": workspace.status}
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(workspace, field, value)
    db.commit()
    db.refresh(workspace)
    audit.log(db, action="updated", user_id=user.id, workspace_id=workspace.id,
              entity_type="workspace", entity_id=workspace.id,
              before_state=before, after_state={"name": workspace.name, "status": workspace.status})
    return workspace
```

- [ ] **Step 5: Register the router in `main.py`**

```python
from app.routers import auth, workspaces
app.include_router(workspaces.router)
```

- [ ] **Step 6: Run tests**

```bash
pytest tests/test_workspaces.py -v
```

Expected: 5 tests PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/app/schemas/workspace.py backend/app/routers/workspaces.py \
        backend/app/main.py backend/tests/test_workspaces.py
git commit -m "feat: workspaces CRUD with membership access control and audit logging"
```

---

## Task 5: Entities + Relationships API

**Files:**
- Create: `backend/app/schemas/entity.py`
- Create: `backend/app/routers/entities.py`
- Create: `backend/tests/test_entities.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Write failing tests — `backend/tests/test_entities.py`**

```python
import pytest

@pytest.fixture
def workspace_id(client, auth_headers):
    return client.post("/workspaces/", json={"name": "Test", "vertical": "fraud"},
                       headers=auth_headers).json()["id"]

def test_create_entity(client, auth_headers, workspace_id):
    response = client.post(f"/workspaces/{workspace_id}/entities", json={
        "type": "organization",
        "name": "Do Good In His Name Inc",
        "data": {"ein": "82-4458479", "sos_id": "4128601"}
    }, headers=auth_headers)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Do Good In His Name Inc"
    assert data["data"]["ein"] == "82-4458479"

def test_list_entities_excludes_deleted(client, auth_headers, workspace_id):
    entity = client.post(f"/workspaces/{workspace_id}/entities",
                         json={"type": "person", "name": "Karen Homan"},
                         headers=auth_headers).json()
    client.delete(f"/workspaces/{workspace_id}/entities/{entity['id']}", headers=auth_headers)
    response = client.get(f"/workspaces/{workspace_id}/entities", headers=auth_headers)
    assert len(response.json()) == 0

def test_create_relationship(client, auth_headers, workspace_id):
    e1 = client.post(f"/workspaces/{workspace_id}/entities",
                     json={"type": "person", "name": "Karen Homan"}, headers=auth_headers).json()
    e2 = client.post(f"/workspaces/{workspace_id}/entities",
                     json={"type": "organization", "name": "Do Good Inc"}, headers=auth_headers).json()
    response = client.post(f"/workspaces/{workspace_id}/relationships", json={
        "entity_a_id": e1["id"],
        "entity_b_id": e2["id"],
        "type": "officer_of",
        "description": "President/Treasurer, $0 salary"
    }, headers=auth_headers)
    assert response.status_code == 201
    assert response.json()["type"] == "officer_of"
```

- [ ] **Step 2: Create `backend/app/schemas/entity.py`**

```python
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class EntityCreate(BaseModel):
    type: str
    name: str
    status: str = "active"
    data: dict = {}

class EntityUpdate(BaseModel):
    name: Optional[str] = None
    status: Optional[str] = None
    data: Optional[dict] = None

class EntityOut(BaseModel):
    id: str
    workspace_id: str
    type: str
    name: str
    status: str
    data: dict
    created_at: datetime
    class Config:
        from_attributes = True

class RelationshipCreate(BaseModel):
    entity_a_id: str
    entity_b_id: str
    type: str
    description: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    source_doc_id: Optional[str] = None

class RelationshipOut(BaseModel):
    id: str
    workspace_id: str
    entity_a_id: str
    entity_b_id: str
    type: str
    description: Optional[str]
    created_at: datetime
    class Config:
        from_attributes = True
```

- [ ] **Step 3: Create `backend/app/routers/entities.py`**

```python
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.entity import Entity, Relationship
from app.models.user import User
from app.schemas.entity import EntityCreate, EntityUpdate, EntityOut, RelationshipCreate, RelationshipOut
from app.services.auth import get_current_user
from app.services import audit
from app.routers.workspaces import get_workspace_or_404

router = APIRouter(prefix="/workspaces/{workspace_id}", tags=["entities"])

@router.post("/entities", response_model=EntityOut, status_code=201)
def create_entity(workspace_id: str, payload: EntityCreate,
                  db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    get_workspace_or_404(workspace_id, user, db)
    entity = Entity(**payload.model_dump(), workspace_id=workspace_id, created_by=user.id)
    db.add(entity)
    db.commit()
    db.refresh(entity)
    audit.log(db, action="created", user_id=user.id, workspace_id=workspace_id,
              entity_type="entity", entity_id=entity.id,
              after_state={"name": entity.name, "type": entity.type})
    return entity

@router.get("/entities", response_model=list[EntityOut])
def list_entities(workspace_id: str, db: Session = Depends(get_db),
                  user: User = Depends(get_current_user)):
    get_workspace_or_404(workspace_id, user, db)
    return db.query(Entity).filter(
        Entity.workspace_id == workspace_id, Entity.is_deleted == False
    ).all()

@router.patch("/entities/{entity_id}", response_model=EntityOut)
def update_entity(workspace_id: str, entity_id: str, payload: EntityUpdate,
                  db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    get_workspace_or_404(workspace_id, user, db)
    entity = db.query(Entity).filter(
        Entity.id == entity_id, Entity.workspace_id == workspace_id
    ).first()
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")
    before = {"name": entity.name, "status": entity.status}
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(entity, field, value)
    db.commit()
    db.refresh(entity)
    audit.log(db, action="updated", user_id=user.id, workspace_id=workspace_id,
              entity_type="entity", entity_id=entity.id, before_state=before)
    return entity

@router.delete("/entities/{entity_id}", status_code=204)
def delete_entity(workspace_id: str, entity_id: str,
                  db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    get_workspace_or_404(workspace_id, user, db)
    entity = db.query(Entity).filter(
        Entity.id == entity_id, Entity.workspace_id == workspace_id
    ).first()
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")
    entity.is_deleted = True
    entity.deleted_at = datetime.now(timezone.utc)
    db.commit()
    audit.log(db, action="deleted", user_id=user.id, workspace_id=workspace_id,
              entity_type="entity", entity_id=entity.id)

@router.post("/relationships", response_model=RelationshipOut, status_code=201)
def create_relationship(workspace_id: str, payload: RelationshipCreate,
                        db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    get_workspace_or_404(workspace_id, user, db)
    rel = Relationship(**payload.model_dump(), workspace_id=workspace_id, created_by=user.id)
    db.add(rel)
    db.commit()
    db.refresh(rel)
    audit.log(db, action="created", user_id=user.id, workspace_id=workspace_id,
              entity_type="relationship", entity_id=rel.id)
    return rel

@router.get("/relationships", response_model=list[RelationshipOut])
def list_relationships(workspace_id: str, db: Session = Depends(get_db),
                       user: User = Depends(get_current_user)):
    get_workspace_or_404(workspace_id, user, db)
    return db.query(Relationship).filter(Relationship.workspace_id == workspace_id).all()
```

- [ ] **Step 4: Register in `main.py`**

```python
from app.routers import auth, workspaces, entities
app.include_router(entities.router)
```

- [ ] **Step 5: Run tests**

```bash
pytest tests/test_entities.py -v
```

Expected: 3 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/schemas/entity.py backend/app/routers/entities.py \
        backend/app/main.py backend/tests/test_entities.py
git commit -m "feat: entities and relationships CRUD with soft delete and audit logging"
```

---

## Task 6: Signal Types + Findings API

**Files:**
- Create: `backend/app/schemas/finding.py`
- Create: `backend/app/routers/findings.py`
- Create: `backend/tests/test_findings.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Write failing tests — `backend/tests/test_findings.py`**

```python
import pytest

@pytest.fixture
def workspace_id(client, auth_headers):
    return client.post("/workspaces/", json={"name": "Test", "vertical": "fraud"},
                       headers=auth_headers).json()["id"]

def test_signal_types_are_preloaded(client, auth_headers):
    response = client.get("/signal-types", headers=auth_headers)
    assert response.status_code == 200
    codes = [s["code"] for s in response.json()]
    assert "SR-003" in codes
    assert "SR-025" in codes
    assert "SR-005" in codes

def test_create_finding(client, auth_headers, workspace_id):
    signal = client.get("/signal-types", headers=auth_headers).json()[0]
    response = client.post(f"/workspaces/{workspace_id}/findings", json={
        "title": "47 Patterson St — 700% overpayment",
        "description": "Paid $300K for $37,490 property. Seller: Winner Kyle J.",
        "severity": "critical",
        "signal_type_id": signal["id"]
    }, headers=auth_headers)
    assert response.status_code == 201
    assert response.json()["status"] == "open"

def test_confirm_finding(client, auth_headers, workspace_id):
    signal = client.get("/signal-types", headers=auth_headers).json()[0]
    finding = client.post(f"/workspaces/{workspace_id}/findings",
                          json={"title": "Test", "severity": "high",
                                "signal_type_id": signal["id"]},
                          headers=auth_headers).json()
    response = client.patch(f"/workspaces/{workspace_id}/findings/{finding['id']}",
                            json={"status": "confirmed"}, headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["status"] == "confirmed"
```

- [ ] **Step 2: Create `backend/app/schemas/finding.py`**

```python
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class SignalTypeOut(BaseModel):
    id: str
    code: str
    name: str
    description: str
    severity: str
    relevant_to: List[str]
    class Config:
        from_attributes = True

class FindingCreate(BaseModel):
    title: str
    description: Optional[str] = None
    severity: str
    signal_type_id: Optional[str] = None

class FindingUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    severity: Optional[str] = None
    status: Optional[str] = None

class FindingOut(BaseModel):
    id: str
    workspace_id: str
    signal_type_id: Optional[str]
    title: str
    description: Optional[str]
    severity: str
    status: str
    created_at: datetime
    class Config:
        from_attributes = True
```

- [ ] **Step 3: Create `backend/app/routers/findings.py`**

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.finding import SignalType, Finding
from app.models.user import User
from app.schemas.finding import SignalTypeOut, FindingCreate, FindingUpdate, FindingOut
from app.services.auth import get_current_user
from app.services import audit
from app.routers.workspaces import get_workspace_or_404

router = APIRouter(tags=["findings"])

# Signal type seed data — from the real Do Good investigation
SIGNAL_TYPES_SEED = [
    {"code": "SR-003", "name": "VALUATION_ANOMALY",
     "description": "Property purchased significantly above or below appraised value",
     "severity": "critical", "relevant_to": ["AG", "IRS"]},
    {"code": "SR-004", "name": "UCC_BURST",
     "description": "Multiple UCC amendments filed within minutes — coordinated lien activity",
     "severity": "high", "relevant_to": ["FCA", "FBI"]},
    {"code": "SR-005", "name": "ZERO_CONSIDERATION",
     "description": "Property transferred for $0 to a private party",
     "severity": "critical", "relevant_to": ["AG", "IRS"]},
    {"code": "SR-015", "name": "DEED_TITLE_DEFECT",
     "description": "Deed executed in favor of an entity that did not legally exist at the time",
     "severity": "high", "relevant_to": ["AG"]},
    {"code": "SR-021", "name": "REVENUE_SPIKE",
     "description": "Organization revenue increased more than 500% year-over-year",
     "severity": "medium", "relevant_to": ["IRS"]},
    {"code": "SR-024", "name": "CHARITY_CONDUIT",
     "description": "Charitable funds used to fund improvements on privately-owned property",
     "severity": "critical", "relevant_to": ["IRS", "AG", "FBI"]},
    {"code": "SR-025", "name": "FALSE_DISCLOSURE",
     "description": "Organization disclosed related-party transactions in one year then denied them in all subsequent years while transactions continued",
     "severity": "critical", "relevant_to": ["IRS", "AG"]},
    {"code": "SR-026", "name": "CONSTRUCTION_OVERAGE",
     "description": "Construction permit value exceeds total organization revenue for that period",
     "severity": "high", "relevant_to": ["IRS", "AG"]},
]

def seed_signal_types(db: Session):
    """Add the signal types if they haven't been added yet."""
    if db.query(SignalType).count() == 0:
        for s in SIGNAL_TYPES_SEED:
            db.add(SignalType(**s))
        db.commit()

@router.get("/signal-types", response_model=list[SignalTypeOut])
def list_signal_types(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    seed_signal_types(db)
    return db.query(SignalType).all()

@router.post("/workspaces/{workspace_id}/findings", response_model=FindingOut, status_code=201)
def create_finding(workspace_id: str, payload: FindingCreate,
                   db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    get_workspace_or_404(workspace_id, user, db)
    finding = Finding(**payload.model_dump(), workspace_id=workspace_id, created_by=user.id)
    db.add(finding)
    db.commit()
    db.refresh(finding)
    audit.log(db, action="created", user_id=user.id, workspace_id=workspace_id,
              entity_type="finding", entity_id=finding.id,
              after_state={"title": finding.title, "severity": finding.severity})
    return finding

@router.get("/workspaces/{workspace_id}/findings", response_model=list[FindingOut])
def list_findings(workspace_id: str, db: Session = Depends(get_db),
                  user: User = Depends(get_current_user)):
    get_workspace_or_404(workspace_id, user, db)
    return db.query(Finding).filter(Finding.workspace_id == workspace_id).all()

@router.patch("/workspaces/{workspace_id}/findings/{finding_id}", response_model=FindingOut)
def update_finding(workspace_id: str, finding_id: str, payload: FindingUpdate,
                   db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    get_workspace_or_404(workspace_id, user, db)
    finding = db.query(Finding).filter(
        Finding.id == finding_id, Finding.workspace_id == workspace_id
    ).first()
    if not finding:
        raise HTTPException(status_code=404, detail="Finding not found")
    before = {"status": finding.status}
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(finding, field, value)
    db.commit()
    db.refresh(finding)
    audit.log(db, action="updated", user_id=user.id, workspace_id=workspace_id,
              entity_type="finding", entity_id=finding.id,
              before_state=before, after_state={"status": finding.status})
    return finding
```

- [ ] **Step 4: Register in `main.py`**

```python
from app.routers import auth, workspaces, entities, findings
app.include_router(findings.router)
```

- [ ] **Step 5: Run tests**

```bash
pytest tests/test_findings.py -v
```

Expected: 3 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/schemas/finding.py backend/app/routers/findings.py \
        backend/app/main.py backend/tests/test_findings.py
git commit -m "feat: signal types with seed data and findings CRUD"
```
