# Verity Prism

An intelligent document processing (IDP) platform that ingests documents, extracts every data point into structured database fields, and makes everything searchable via plain English queries.

Fraud investigation is the proving ground. The same engine runs insurance, legal, and compliance verticals without modification.

---

## What Works Now

**Document ingestion pipeline**
- Upload PDF, image, or XML → SHA-256 hash (evidence lock) → OCR → type detection → field extraction → full-text search index
- Background processing: upload returns immediately, pipeline runs async
- 11 document type schemas: DEED, 990, SOS-FILING, UCC, PARCEL-RECORD, BUILDING-PERMIT, AUDIT-REPORT, SCREENSHOT, OBITUARY, PLAT, CORRESPONDENCE
- XML direct parse for structured files (IRS 990 XML → 1.0 confidence, no OCR needed)
- Unknown document types auto-create investigation leads instead of silently failing

**Extraction engine**
- Schema-driven: adding a new document type is one database row — no code change
- One row per extracted field per document (`document_extractions` table) — every field individually queryable
- Confidence scores per field; extraction errors stored and surfaced in the UI
- Vertical-aware schema lookup: fraud-specific schemas only activate in fraud workspaces

**Document viewer**
- Split-pane view: source PDF (65%) + extracted fields panel (35%)
- react-pdf renders in-browser — no plugin or external viewer required
- Each document has its own URL; document list stays visible with selected doc highlighted
- Status-aware fields panel: surfaces `extraction_error` text on extraction failure

**NLP search**
- Plain English queries → PostgreSQL full-text search + field-level filters on `document_extractions`
- Numeric guard prevents CAST crashes on non-numeric values
- No SQL required

**Agentic AI chat**
- Native Anthropic tool-use loop (up to 10 rounds, synthesis pass fallback)
- 6 workspace-scoped read-only tools: `search_documents`, `get_entity`, `query_extractions`, `get_transactions`, `get_findings`, `get_leads`
- `workspace_id` injected by dispatcher — Claude cannot access data outside the current workspace
- Vertical tool registry: fraud workspaces get additional tools; engine tools ship to all verticals

**Platform**
- JWT authentication, workspace isolation, role-aware access
- Immutable audit log (PostgreSQL trigger blocks UPDATE/DELETE at DB level)
- Soft deletes everywhere — nothing is permanently removed
- Schema library: browse all active document types, field definitions, parse strategies at `/schemas`
- Vertical-aware UI: General workspaces show engine nav; Fraud workspaces add Transactions, Findings, Leads

**Test coverage**
- 80 tests, all passing — auth, workspaces, documents, extractions, entities, findings, transactions, leads, notes, search, AI chat, agentic tool loop

---

## Quick Start

```bash
# Copy and fill in your Anthropic API key
cp backend/.env.example backend/.env

# Start everything
docker-compose up --build
```

| Service | URL |
|---|---|
| Frontend | http://localhost:5173 |
| Backend API | http://localhost:8000 |
| API docs | http://localhost:8000/docs |

**Seed document schemas** (required on first run):
```bash
docker-compose exec backend python -m app.seeds.document_schemas
```

---

## Architecture

```
Documents → Ingestion Pipeline → Extraction Engine → Knowledge Base → Verticals → UI
              (hash, OCR,          (type detect,        (PostgreSQL,    (fraud,
               store)               field extract)       FTS, audit)     insurance, ...)
```

**Engine vs. cap:** The engine ships to every customer. A vertical cap installs on top — schema sets, signal definitions, workflow config, export formats. The fraud cap never ships to an insurance customer. Adding a new vertical means writing a cap, not modifying the engine.

**`document_extractions` is the central table.** One row per extracted field per document. A deed with 64 fields = 64 rows. Every data point is individually queryable without JSON parsing.

**`document_schemas` drives everything.** `parse_strategy` (`claude` or `xml_direct`) tells the pipeline how to extract. `vertical` scopes a schema to a specific vertical or `general` for all. No code change to add a new document type.

---

## Build Journal

8 posts on how and why this platform was built — not feature announcements, but the reasoning behind specific decisions: why the database is structured the way it is, why the AI agent uses tool use instead of context injection, how a real document set shaped the schema design.

[From Case to Code](https://corvus-0x.hashnode.dev) on Hashnode.

---

## Stack

| Layer | Technology |
|---|---|
| Frontend | React 18 + Vite + Tailwind CSS |
| Backend | Python 3.12 + FastAPI |
| Database | PostgreSQL 16 |
| ORM + Migrations | SQLAlchemy 2.0 + Alembic (5 migrations) |
| AI | Anthropic Claude API (claude-sonnet-4-6) |
| OCR | PyMuPDF + pytesseract |
| Auth | JWT (python-jose + passlib/bcrypt) |
| PDF rendering | react-pdf (pdf.js) |
| Containers | Docker + docker-compose |

---

## Documentation

**Start here if you want to understand the architecture:**

- [`docs/decisions/`](docs/decisions/) — Architecture Decision Records: why the database is structured as row-per-field, why adding a document type requires no code change, why the engine knows nothing about fraud or insurance, why SSE uses fetch+ReadableStream instead of native EventSource
- [`docs/roadmap.md`](docs/roadmap.md) — phase status, what's complete, what's next, and why each phase gates the next
- [`docs/build-inventory.md`](docs/build-inventory.md) — every component, what it does, what it connects to, and what's planned
- [`docs/superpowers/specs/`](docs/superpowers/specs/) — design specifications written before each build
- [`docs/superpowers/plans/`](docs/superpowers/plans/) — implementation plans

---

*Built by [Corvus](https://corvus-0x.hashnode.dev)*
