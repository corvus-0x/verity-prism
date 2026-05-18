# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## What This Is

**Verity Prism** — An **Intelligent Document Processing (IDP) platform** built by Verity. that ingests documents, extracts every data point into structured database fields, and makes everything searchable via plain English queries. Fraud investigation is Vertical 1 (the proving ground). Insurance automation is Vertical 2. Additional verticals follow.

Full design spec: `docs/superpowers/specs/2026-05-17-phase1-core-foundation-design.md`
Implementation plans: `docs/superpowers/plans/`
Private/sensitive case files: `private/` (gitignored — never commit)

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React + Vite |
| Backend | Python 3.12 + FastAPI |
| Database | PostgreSQL 16 |
| ORM + Migrations | SQLAlchemy 2.0 + Alembic |
| AI | Claude API (claude-sonnet-4-6) |
| OCR | PyMuPDF + pytesseract |
| Auth | JWT (python-jose + passlib/bcrypt) |
| Containers | Docker + docker-compose |

---

## Common Commands

### Start everything
```bash
docker-compose up --build
```
Frontend: `http://localhost:5173` | Backend API: `http://localhost:8000` | API docs: `http://localhost:8000/docs`

### Backend only (faster iteration)
```bash
cd backend
uvicorn app.main:app --reload
```

### Run all tests
```bash
cd backend
pytest tests/ -v
```

### Run a single test file
```bash
pytest tests/test_documents.py -v
```

### Run one specific test
```bash
pytest tests/test_documents.py::test_upload_creates_document_record -v
```

### Database migrations
```bash
cd backend
alembic revision --autogenerate -m "description of change"
alembic upgrade head
alembic downgrade -1   # roll back one step
```

### Connect to the database directly
```bash
docker-compose exec db psql -U catalyst -d catalyst
```

---

## Architecture

### Five-layer system

```
Document Sources → Ingestion → Extraction Pipeline → Knowledge Base → Verticals → UI
```

**Layer 2 (Extraction)** is the IDP core — Claude detects document type, selects the matching schema from `document_schemas`, extracts every field into `document_extractions` (one row per field), then updates the FTS search index.

**Layer 4 (Verticals)** is where fraud-specific logic lives — signal types, findings, investigation leads. These are modules built on top of the IDP core, not baked into it.

### Backend layout

Routers are thin: validate input → call service → return response. Business logic lives in `app/services/`.

```
app/
├── routers/       # HTTP endpoints — thin, call services
├── services/      # Business logic — document_pipeline, extraction_engine, search_service, ai_engine, audit
├── models/        # SQLAlchemy ORM models — one file per table group
├── schemas/       # Pydantic request/response models
└── main.py        # FastAPI app, routers registered here
```

### Key design decisions

**`document_extractions` is the central IDP table.** One row per extracted field per document. A deed with 11 fields = 11 rows. This makes every data point individually queryable without JSON parsing.

**`document_schemas` drives AI extraction.** Each document type (DEED, 990, UCC, etc.) has a schema defining what fields to extract and the prompt to use. Schemas are in the database so they can be updated without redeploying.

**`workspaces` is the general term** for what the fraud vertical UI calls a "Case." The backend always uses `workspace_id`. Frontend labels it per vertical.

**Audit log is immutable.** A PostgreSQL trigger (`audit_log_immutable`) prevents UPDATE or DELETE on `audit_log` at the database level — not just in code. Call `audit.log()` from services after every meaningful action.

**SHA-256 hash is always first.** In `document_pipeline.py`, the hash is computed before OCR, before extraction, before naming. This is the evidence lock.

**Soft deletes everywhere.** Nothing is hard-deleted. Set `is_deleted = True` and `deleted_at = now()`. Filter active records with `.filter(Entity.is_deleted == False)`.

### NLP Search

User query → `search_service.py` → Claude translates to structured filters → PostgreSQL FTS (`search_vector @@ plainto_tsquery(...)`) + field-level filters on `document_extractions` → document cards with matched fields.

The `documents.search_vector` column is a `tsvector` updated after every extraction to include both OCR text and extracted field values.

### AI Chat context

`ai_engine.build_workspace_context()` loads entities, transactions, findings, open leads, and document list into a text block. This is the system prompt context for every chat message. Richer workspace data = better answers.

---

## Test Conventions

- Test database: `catalyst_test` (separate from dev database)
- `conftest.py` drops and recreates all tables before each test — every test starts clean
- `auth_headers` fixture handles login and returns `{"Authorization": "Bearer <token>"}`
- `workspace_id` fixture creates a workspace and returns its ID
- Mock Claude API calls with `unittest.mock.patch("app.services.<module>.Anthropic")`
- TDD: write the failing test first, confirm it fails, then implement

---

## Environment Variables

Required in `backend/.env` (copy from `backend/.env.example`):
```
DATABASE_URL=postgresql://catalyst:catalyst@localhost:5432/catalyst
SECRET_KEY=<long random string>
ANTHROPIC_API_KEY=sk-ant-...
UPLOAD_DIR=./uploads
```

---

## What Is Not Built Yet

Phase 1 backend is the current build target. Frontend, public data integrations (IRS TEOS, Ohio SOS), network graph, referral generation, and team collaboration are later phases. See `docs/superpowers/plans/` for the full task breakdown.
