# Verity Prism

An intelligent document processing (IDP) platform that ingests documents, extracts every data point into structured database fields, and makes everything searchable via plain English queries.

Fraud investigation is the proving ground. The same engine runs insurance, legal, and compliance verticals without modification.

---

## What Works Now

**Document ingestion pipeline**
- Upload PDF, image, or XML → SHA-256 hash (evidence lock) → OCR at 300 DPI → type detection → field extraction → full-text search index
- Background processing: upload returns immediately, pipeline runs async
- Partial batch retry: failed extraction batches retried once before routing to human review
- 11 document type schemas: DEED, 990, SOS-FILING, UCC, PARCEL-RECORD, BUILDING-PERMIT, AUDIT-REPORT, SCREENSHOT, OBITUARY, PLAT, CORRESPONDENCE
- XML direct parse for structured files (IRS 990 XML → 1.0 confidence, no OCR needed)
- Unknown document types auto-create investigation leads instead of silently failing

**Extraction engine**
- Schema-driven: adding a new document type is one database row — no code change
- One row per extracted field per document (`document_extractions` table) — every field individually queryable
- **Dual confidence per field**: AI confidence (model certainty) + OCR confidence (text clarity) — distinguishes scan quality problems from schema prompt problems
- Per-field confidence thresholds: high-stakes fields (EIN, sale_amount) can require tighter confidence than low-stakes fields
- Field validation rules: `required`, `min_length`, `max_length`, `regex` per field in schema definition
- Schema fields grouped into document-logical sections (Parties, Financial, Property, Recording etc.) for the review form
- Vertical-aware schema lookup: fraud-specific schemas only activate in fraud workspaces

**Document viewer + review pane**
- Split-pane view: source PDF (65%) + fields panel (35%)
- react-pdf renders in-browser — no plugin or external viewer required
- **Full document review pane** (`?review=1`): schema-driven form shows every defined field whether extracted or not
  - Four field states: auto-extracted (high confidence), low confidence, not extracted, source obscured
  - Active field highlights its location on the PDF with a blue box and label
  - Clicking a field searches the PDF text layer for its value; ← → navigates multiple matches
  - Operator corrections store a PDF region capture (page, bounding box, base64 image, note) as evidence
  - "Save all" commits all pending corrections in one action
- Document flagging: structured rejection reasons (unknown type, missing pages, low quality scan etc.) with optional note, travel through audit trail

**NLP search**
- Plain English queries → PostgreSQL full-text search + field-level filters on `document_extractions`
- Numeric guard prevents CAST crashes on non-numeric values
- No SQL required

**Agentic AI chat**
- Native Anthropic tool-use loop (up to 10 rounds, synthesis pass fallback)
- 6 workspace-scoped read-only tools: `search_documents`, `get_entity`, `query_extractions`, `get_transactions`, `get_findings`, `get_leads`
- `workspace_id` injected by dispatcher — Claude cannot access data outside the current workspace
- Vertical tool registry: fraud workspaces get additional tools; engine tools ship to all verticals

**Observability dashboard** (`/observability`)
- Automation Rate: % of documents processed straight-through vs requiring human review
- Inbound/Completed volume trend over the last 30 days
- Extraction quality by schema: avg AI confidence, avg OCR confidence, retry rate, correction rate
- Current processing: pending + review queue counts

**Platform**
- JWT authentication (httpOnly cookie + Bearer hybrid), workspace isolation, role-aware access
- Immutable audit log (PostgreSQL trigger blocks UPDATE/DELETE at DB level)
- Soft deletes everywhere — nothing is permanently removed
- Schema library: browse all active document types, field definitions, parse strategies at `/schemas`
- Vertical-aware UI: General workspaces show engine nav; Fraud workspaces add Transactions, Findings, Leads

**Test coverage**
- 171 tests, all passing — auth, workspaces, documents, extractions, entities, findings, transactions, leads, notes, search, AI chat, agentic tool loop, observability, schema review

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

**Run database migrations** (required after any pull):
```bash
cd backend && alembic upgrade head
```

---

## Architecture

```
Documents → Ingestion Pipeline → Extraction Engine → Knowledge Base → Verticals → UI
              (hash, OCR,          (type detect,        (PostgreSQL,    (fraud,
               store)               field extract)       FTS, audit)     insurance, ...)
```

**Engine vs. cap:** The engine ships to every customer. A vertical cap installs on top — schema sets, signal definitions, workflow config, export formats. The fraud cap never ships to an insurance customer. Adding a new vertical means writing a cap, not modifying the engine.

**`document_extractions` is the central table.** One row per extracted field per document. A deed with 64 fields = 64 rows. Every data point is individually queryable without JSON parsing. Each row carries both AI confidence and OCR confidence for diagnostics.

**`document_schemas` drives everything.** `parse_strategy` (`claude` or `xml_direct`) tells the pipeline how to extract. `vertical` scopes a schema to a specific vertical or `general` for all. `schema_fields` JSON defines each field with name, type, description, group, optional thresholds, and optional validation rules. No code change to add a new document type.

---

## Build Journal

11 posts on how and why this platform was built — not feature announcements, but the reasoning behind specific decisions: why the database is structured the way it is, why the AI agent uses tool use instead of context injection, how a real document set shaped the schema design, what the audit found that wasn't there, and why surfacing a problem without a fix is as bad as not detecting it.

[From Case to Code](https://corvus-0x.hashnode.dev) on Hashnode.

---

## Stack

| Layer | Technology |
|---|---|
| Frontend | React 18 + Vite + Tailwind CSS + Recharts |
| Backend | Python 3.12 + FastAPI |
| Database | PostgreSQL 16 |
| ORM + Migrations | SQLAlchemy 2.0 + Alembic (9 migrations) |
| AI | Anthropic Claude API (claude-sonnet-4-6) |
| OCR | PyMuPDF + pytesseract (300 DPI) |
| Auth | JWT via httpOnly cookie + Bearer (python-jose + passlib/bcrypt) |
| PDF rendering | react-pdf (pdf.js, text layer enabled) |
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
