# Verity Prism — Build Inventory

**Purpose:** Every component that exists, what it does, what it connects to, and whether it's wired in.  
**Rule:** Nothing gets built without adding it here. Update this at the end of every session.  
**Status key:** ✅ Connected — wired into main flow | ⚠️ Loose — built but not yet integrated | 🔲 Planned — in a plan but not built

---

## How to Use This

When you build something new, ask three questions:
1. What does this component do?
2. What does it call, and what calls it?
3. Is it wired into the platform, or is it floating?

If the answer to #3 is "floating," add it here with status ⚠️ and note where it needs to connect in a future phase. That's the thing that broke Catalyst — built pieces with no documented home.

---

## Scripts (Standalone Utilities)

### `scripts/fetch_990_xml.py`
**What it does:** Downloads 990 XML filings from IRS TEOS bulk data for any organization by EIN. Handles all IRS ZIP formats (monthly 2023+, year-wide 2021-2022, CT1 legacy 2020, Deflate64 compression). Uses HTTP range requests to read ZIP table-of-contents without downloading full archives.

**Currently used:** Manually from terminal — `python scripts/fetch_990_xml.py --ein XXXXXXXXX`

**Calls:** IRS bulk data URLs directly (no internal dependencies)

**Called by:** Nothing in the platform yet

**Needs to connect to (Phase 2):**
- New service: `app/services/public_data.py` — wraps the download logic
- New endpoint: `POST /workspaces/{id}/import/990?ein=XXXXXXXXX`
- That endpoint calls `create_pending_document()` + `process_upload_background()` for each downloaded XML

**Status:** ⚠️ LOOSE — works, tested against live IRS data, not wired into platform

---

### `scripts/parse_990_xml.py`
**What it does:** Reads all 990 XML files in `private/example documents/990_xml/` and prints a structured report — revenue, expenses, balance sheet, governance flags, officers, program service revenue, and schedules. Used for investigation analysis, not for platform processing.

**Currently used:** Manually for investigation analysis — `python scripts/parse_990_xml.py`

**Calls:** Python standard library only (xml.etree.ElementTree)

**Called by:** Nothing in the platform

**Needs to connect to:** This is an investigator tool, not a platform component. It can stay as a CLI utility. Consider wrapping it as a workspace report endpoint in Phase 2.

**Status:** ⚠️ LOOSE — investigation utility, intentionally standalone for now

---

## Database Models (`backend/app/models/`)

### `user.py` — Users table
**What it does:** Stores accounts. Fields: id, email, password_hash, full_name, role.
**Called by:** auth router, get_current_user dependency, workspace_members
**Status:** ✅ Connected

### `workspace.py` — Workspaces + WorkspaceMembers tables
**What it does:** A workspace is a case container. WorkspaceMember tracks who has access at what role.
**Called by:** All workspace-scoped routers. Every entity, document, finding, etc. has a workspace_id.
**Status:** ✅ Connected

### `document.py` — Documents table
**What it does:** One row per uploaded file. Stores: sha256_hash, file_path, detected_doc_type, extraction_status (`pending`/`complete`/`failed`/`no_schema`), extraction_error, ocr_text, search_vector.
**Called by:** document_pipeline.py, documents router, search_service (Task 9)
**Note:** `extraction_status = no_schema` triggers auto-lead creation in the pipeline. `extraction_error` stores the reason for failures.
**Status:** ✅ Connected

### `document_schema.py` — DocumentSchemas table
**What it does:** The extraction schema registry. One row per document type (DEED, 990, UCC, etc.) with schema_fields (JSON array of field definitions) and extraction_prompt.
**Called by:** extraction_engine.py (`get_schema_for_type`), xml_parser.py, document_pipeline.py
**Note:** 11 schemas are seeded. Adding a new schema requires no code change — just add a row.
**Status:** ✅ Connected

### `document_extraction.py` — DocumentExtractions table
**What it does:** The central IDP table. One row per extracted field per document. A 340-field parcel record creates 340 rows. Every field is individually queryable.
**Called by:** extraction_engine.py (`save_extractions`), xml_parser.py (`parse_xml_document`), search_service (Task 9)
**Status:** ✅ Connected

### `entity.py` — Entities + Relationships tables
**What it does:** People and organizations under investigation. Soft-deleted. Relationships link entities (officer_of, owner_of, etc.).
**Called by:** entities router, ai_engine.py (Task 10 workspace context)
**Status:** ✅ Connected

### `transaction.py` — Transactions table
**What it does:** Financial movements tied to workspace entities.
**Called by:** transactions router, ai_engine.py (Task 10)
**Status:** ✅ Connected

### `finding.py` — SignalTypes + Findings + FindingEvidence tables
**What it does:** Signal types are the fraud pattern catalog (SR-003 through SR-026). Findings are confirmed signals in a workspace. FindingEvidence links findings to documents.
**Called by:** findings router, ai_engine.py (Task 10)
**Note:** Signal type seed data is in `findings.py` router (8 signal types pre-loaded).
**Status:** ✅ Connected

### `lead.py` — InvestigationLeads table
**What it does:** Open questions and next steps. Can be created by users OR auto-created by the pipeline when a document has no schema.
**Called by:** leads router, document_pipeline.py (`_no_schema` handler)
**Status:** ✅ Connected

### `note.py` — Notes table
**What it does:** Analyst observations attached to any workspace entity (workspace, entity, document, finding, transaction, lead).
**Called by:** notes router
**Status:** ✅ Connected

### `ai.py` — AIConversations + AIMessages tables
**What it does:** Stores chat sessions with Claude for each workspace.
**Called by:** ai router (Task 10), ai_engine.py (Task 10)
**Status:** 🔲 Planned — model exists, router/service not built (Task 10)

### `audit.py` — AuditLog table
**What it does:** Immutable record of every action. PostgreSQL trigger blocks UPDATE/DELETE at the database level.
**Called by:** audit.py service, called from every router and the pipeline after meaningful actions
**Status:** ✅ Connected

---

## Services (`backend/app/services/`)

### `audit.py` — Audit log writer
**What it does:** `log()` writes one permanent row to audit_log. The database trigger makes it immutable.
**Called by:** Every router (create/update/delete operations) and document_pipeline.py
**Calls:** AuditLog model
**Status:** ✅ Connected

### `auth.py` — Authentication
**What it does:** `hash_password`, `verify_password`, `create_access_token`, `get_current_user`. The `get_current_user` dependency protects every authenticated endpoint.
**Called by:** auth router, every protected router via `Depends(get_current_user)`
**Calls:** User model, JWT, bcrypt
**Status:** ✅ Connected

### `ocr.py` — Text extraction
**What it does:** Extracts text from PDFs (embedded text first, OCR fallback for scanned pages) and images. Entry point: `extract_text(file_bytes, file_type)`.
**Called by:** document_pipeline.py (Step 3)
**Calls:** PyMuPDF (fitz), pytesseract, Pillow
**Status:** ✅ Connected

### `extraction_engine.py` — Claude-based extraction
**What it does:** Three functions:
- `detect_document_type(ocr_text)` — asks Claude to identify the document type
- `get_schema_for_type(doc_type, db)` — looks up the active schema
- `extract_fields(ocr_text, schema)` + `save_extractions(...)` — Claude extracts fields, saves to document_extractions
**Called by:** document_pipeline.py (Steps 4, 5, 6)
**Calls:** Anthropic API, DocumentSchema model, DocumentExtraction model
**Status:** ✅ Connected

### `naming.py` — Standardized filename generation
**What it does:** `generate_standardized_name(ocr_text, filename, ext)` — asks Claude to generate a standardized filename in the format `YYYY-MM-DD_DOC-TYPE_ENTITY_DESCRIPTION.ext`.
**Called by:** document_pipeline.py (Step 7)
**Calls:** Anthropic API
**Status:** ✅ Connected

### `xml_parser.py` — Direct XML extraction
**What it does:** `parse_xml_document(file_bytes, schema, ...)` — for structured XML files (990, 990-T), reads field values directly from XML element paths defined in schema descriptions. Bypasses OCR and Claude. Confidence = 1.0.
**Called by:** document_pipeline.py (Step 6, XML branch)
**Calls:** xml.etree.ElementTree, DocumentExtraction model
**Note:** `is_parseable_xml(file_bytes, doc_type)` is the gate — returns True only for 990/990-T XML files.
**Status:** ✅ Connected

### `document_pipeline.py` — Upload orchestrator
**What it does:** Two functions:
- `create_pending_document()` — hash, store file, create pending DB record (runs before HTTP response)
- `process_upload_background()` — full pipeline (OCR → type detection → schema lookup → extraction → FTS index → audit). Runs after HTTP response via BackgroundTasks.
**Called by:** documents router
**Calls:** ocr.py, extraction_engine.py, xml_parser.py, naming.py, audit.py, InvestigationLead model (for no_schema)
**Status:** ✅ Connected

### `search_service.py` — NLP search
**What it does:** Translates plain-English queries into PostgreSQL FTS + field-level filters on document_extractions.
**Called by:** search router (Task 9)
**Calls:** Anthropic API, Document model, DocumentExtraction model
**Status:** 🔲 Planned (Task 9)

### `ai_engine.py` — AI chat
**What it does:** Builds workspace context (entities, transactions, findings, documents) and passes it to Claude for conversational analysis.
**Called by:** ai router (Task 10)
**Calls:** Anthropic API, all workspace models
**Status:** 🔲 Planned (Task 10)

---

## API Routers (`backend/app/routers/`)

| Router | Endpoints | Status |
|---|---|---|
| `auth.py` | POST /auth/register, POST /auth/login | ✅ |
| `workspaces.py` | CRUD /workspaces, /workspaces/{id}/members | ✅ |
| `entities.py` | CRUD /workspaces/{id}/entities, /relationships | ✅ |
| `findings.py` | GET /signal-types, CRUD /workspaces/{id}/findings | ✅ |
| `transactions.py` | CRUD /workspaces/{id}/transactions | ✅ |
| `leads.py` | CRUD /workspaces/{id}/leads | ✅ |
| `notes.py` | CRUD /workspaces/{id}/notes | ✅ |
| `documents.py` | POST /workspaces/{id}/documents, GET list/detail/extractions | ✅ |
| `search.py` | POST /workspaces/{id}/search | 🔲 Task 9 |
| `ai.py` | POST /workspaces/{id}/conversations + messages | 🔲 Task 10 |

---

## Document Schemas (database — `document_schemas` table)

All 11 schemas are seeded and active. The pipeline uses them automatically when a document of the matching type is uploaded.

| Schema | Fields | XML parse? | Phase 2 additions needed |
|---|---|---|---|
| PARCEL-RECORD | 370 | No (county website HTML) | Direct scraper from county auditor portals |
| DEED | 64 | No (PDFs) | None — complete |
| 990 | 235 | **Yes** (IRS XML) | Wire `fetch_990_xml.py` into platform import endpoint |
| SOS-FILING | 47 | No (PDFs) | Ohio SOS API integration (Phase 2) |
| UCC | 46 | No (PDFs) | Ohio SOS UCC search API (Phase 2) |
| BUILDING-PERMIT | 13 | No (Excel/PDF) | County permit portal scrapers (Phase 2) |
| AUDIT-REPORT | 122 | No (PDFs) | Ohio AOS bulk download (Phase 2) |
| SCREENSHOT | 26 | No (images/PDFs) | None — complete |
| OBITUARY | 63 | No (PDFs) | None — complete |
| PLAT | 51 | No (PDFs) | None — complete |
| CORRESPONDENCE | 59 | No (PDFs/Word) | None — complete |

---

## Seeds (`backend/app/seeds/`)

### `document_schemas.py`
**What it does:** Seeds all 11 document type schemas into the `document_schemas` table. Idempotent — skips existing schemas, adds new ones.
**How to run:** `docker-compose exec backend python -m app.seeds.document_schemas`
**How to add a new schema:** Add a `seed_X_schema(db)` function following the existing pattern, then add it to `main()`.
**Status:** ✅ Connected — runs on demand, not on startup

---

## Infrastructure

### Docker + docker-compose
**What it does:** Runs the full stack (PostgreSQL, FastAPI backend) in containers. `docker-compose up -d` starts everything.
**Status:** ✅ Connected

### Alembic migrations
**What it does:** Tracks and applies database schema changes. `alembic upgrade head` runs pending migrations.
**Current migration:** `5a4ff7266708_initial_schema.py` — creates all 17 tables
**Manual DB changes this session:** Added `no_schema` enum value + `extraction_error` column directly via SQL (not yet in a migration file)
**⚠️ Note:** The `no_schema` enum value and `extraction_error` column were added directly to the live database but are NOT in an Alembic migration. If you rebuild from scratch, `alembic upgrade head` will not create them. Need a migration.
**Status:** ⚠️ LOOSE — needs a migration for the Task 8 database changes

### FTS Index + Audit Trigger
**What it does:** GIN index on `documents.search_vector` for fast full-text search. PostgreSQL trigger on `audit_log` blocking UPDATE/DELETE.
**Status:** ✅ Applied via SQL in Task 2 — lives in the database

---

## Test Coverage (`backend/tests/`)

| Test file | What it covers | Passing |
|---|---|---|
| `test_auth.py` | Register, login, bad password, token validation | ✅ 5/5 |
| `test_workspaces.py` | Create, list, get, update, access control | ✅ 5/5 |
| `test_entities.py` | Create, soft delete, relationships | ✅ 3/3 |
| `test_findings.py` | Signal type preload, create, confirm | ✅ 3/3 |
| `test_transactions.py` | Create, list | ✅ 2/2 |
| `test_leads.py` | Create, complete with summary | ✅ 2/2 |
| `test_notes.py` | Create, filter by entity | ✅ 2/2 |
| `test_documents.py` | Upload, hash, preserve filename, list, empty file | ✅ 5/5 |
| `test_extractions.py` | Upload with mock Claude, pending status | ✅ 2/2 |
| **Total** | | **29/29** |

**Not yet tested:**
- Search service (Task 9)
- AI chat (Task 10)
- Background pipeline completing in test environment (session isolation prevents full pipeline test — see diary)
- XML direct parse path (tested manually, not in automated suite)

---

## Phase 2 Integration Map

Everything marked ⚠️ LOOSE or 🔲 Planned needs a home in Phase 2 plans. This is the connection map:

```
scripts/fetch_990_xml.py
    → Phase 2: app/services/public_data.py
    → Phase 2: POST /workspaces/{id}/import/990
    → calls: create_pending_document() + process_upload_background()

scripts/parse_990_xml.py
    → Stay as CLI investigator tool
    → Optional Phase 2: GET /workspaces/{id}/990-summary endpoint

Alembic migration needed:
    → Add no_schema to extraction_status enum
    → Add extraction_error VARCHAR column to documents table

Phase 2 endpoints not yet planned:
    → POST /workspaces/{id}/import/990 (EIN → IRS fetch → pipeline)
    → POST /workspaces/{id}/import/ucc (SOS search → pipeline)
    → POST /workspaces/{id}/import/sos (SOS entity lookup → pipeline)
    → GET  /workspaces/{id}/network-graph (entity relationship visualization)
    → POST /workspaces/{id}/referral (generate referral package)
```

---

## Update Log

| Date | What changed |
|---|---|
| 2026-05-19 | Initial inventory created. Tasks 1-8 complete. 29/29 tests. |
| 2026-05-19 | 11 document schemas seeded. fetch_990_xml.py and parse_990_xml.py built. |
