# Verity Prism — Build Inventory

**Purpose:** Every component that exists, what it does, what it connects to, and whether it's wired in.  
**Rule:** Nothing gets built without adding it here. Update at the end of every session.  
**Status key:** ✅ Connected | ⚠️ Loose — built but not yet integrated | 🔲 Planned — not yet built

---

## Architecture: Engine vs. Cap

Everything in this inventory belongs to one of two layers:

**ENGINE** — Ships to every customer, every vertical. Contains no domain logic. Processes documents, extracts fields, indexes data, answers queries.

**VERTICAL CAP** — Installs on top of the engine for a specific domain. Contains signal definitions, schema sets, workflow config, export formats. A fraud customer never sees insurance cap logic. An insurance customer never sees fraud cap logic.

This distinction matters in code: if a component knows what fraud is, it belongs in the fraud cap, not the engine.

---

## ENGINE COMPONENTS

### Scripts — Standalone Utilities

#### `scripts/fetch_990_xml.py` — IRS 990 XML Downloader
**Layer:** Engine (general-purpose, any vertical pulls 990s)  
**What it does:** Downloads 990 XML from IRS TEOS bulk data for any EIN. Handles all ZIP formats (monthly 2023+, year-wide 2021-2022, CT1 legacy 2020, Deflate64 compression). HTTP range requests read ZIP table-of-contents without downloading full archives.  
**Currently used:** CLI only — `python scripts/fetch_990_xml.py --ein XXXXXXXXX`  
**Needs to connect to (Phase 2):** `app/services/connectors/irs_teos.py` → `POST /workspaces/{id}/connectors/irs-teos`  
**Status:** ⚠️ LOOSE — works, not wired into platform

#### `scripts/parse_990_xml.py` — 990 Analysis Utility
**Layer:** Engine (investigator tool, any vertical)  
**What it does:** Reads all 990 XML files and prints structured financial/governance report. Investigation analysis tool, not platform processing.  
**Currently used:** CLI only — `python scripts/parse_990_xml.py`  
**Needs to connect to:** Stay as CLI utility. Optional Phase 2: workspace report endpoint.  
**Status:** ⚠️ LOOSE — intentionally standalone

---

### Database Models (`backend/app/models/`)

#### `user.py` ✅
Engine. Accounts, authentication. No domain logic.

#### `workspace.py` ✅
Engine. A workspace is a case/claim/matter container — vertical-agnostic. WorkspaceMember tracks access. The `vertical` field on Workspace tells the signal engine which cap to apply.

#### `document.py` ✅
Engine. One row per uploaded file. `extraction_status` (`pending`/`complete`/`failed`/`no_schema`), `extraction_error`. Hash, OCR text, search vector. No domain knowledge.

#### `document_schema.py` ✅
Engine. The schema registry. `vertical = "general"` means available in all workspaces. `vertical = "fraud"` activates only in fraud workspaces. `vertical = "insurance"` activates only in insurance workspaces. Currently all 11 schemas are `general`.

#### `document_extraction.py` ✅
Engine. **The central IDP table.** One row per extracted field per document. No domain knowledge — just field_name, field_value, field_type, confidence. Every vertical's signals query this table.

#### `entity.py` ✅
Engine. People and organizations. Soft-deleted. Relationships link entities. No fraud-specific fields.

#### `transaction.py` ✅
Engine. Financial movements. Generic enough for fraud, insurance, legal — any domain that tracks money.

#### `finding.py` ✅
Engine structure, **vertical content.** The `Finding` and `FindingEvidence` models are engine components. The `SignalType` seed data (SR-003, SR-025, etc.) is **fraud cap content** — currently seeded in the findings router but should move to a fraud cap installer in Phase 3.

#### `lead.py` ✅
Engine. Investigation leads / open questions. Auto-created by pipeline for no_schema documents. Generic across verticals.

#### `note.py` ✅
Engine. Analyst observations on any entity type.

#### `ai.py` 🔲
Engine. AIConversation + AIMessage. Model exists, router/service not built (Task 10).

#### `audit.py` ✅
Engine. Immutable audit log. PostgreSQL trigger blocks UPDATE/DELETE at database level.

---

### Services (`backend/app/services/`)

#### `audit.py` ✅
Engine. `log()` writes permanent audit rows. Called from every router and the pipeline.

#### `auth.py` ✅
Engine. JWT creation/verification, bcrypt hashing, `get_current_user` dependency.

#### `ocr.py` ✅
Engine. Text extraction from PDFs and images. PyMuPDF for embedded text, pytesseract for scanned pages. Entry point: `extract_text(file_bytes, file_type)`.

#### `extraction_engine.py` ✅
Engine. Three functions:
- `detect_document_type()` — asks Claude to identify type from OCR text
- `get_schema_for_type(doc_type, db, workspace_vertical)` — vertical-aware schema lookup. Prefers vertical-specific schema; falls back to `general`. A fraud workspace gets fraud schemas first, then general. Prevents cross-vertical schema contamination.
- `extract_fields()` + `save_extractions()` — Claude extracts fields per schema definition, returns `list[dict]`

#### `naming.py` ✅
Engine. Generates standardized filenames: `YYYY-MM-DD_DOC-TYPE_ENTITY_DESCRIPTION.ext`.

#### `xml_parser.py` ✅
Engine. Direct XML parse for structured files. Reads field values from element paths in schema descriptions. Returns `list[dict]` — same format as `extract_fields()`. The pipeline calls `save_extractions()` identically for both paths. Confidence = 1.0. Currently active for 990 and 990-T.

#### `document_pipeline.py` ✅
Engine. Orchestrates the full upload pipeline:
- `create_pending_document()` — hash + store + pending record (before HTTP response)
- `process_upload_background()` — OCR → type → **vertical-aware** schema lookup → extract → FTS → audit (after response via BackgroundTasks)
- `_no_schema()` — creates investigation lead for unknown document types
- `_fail()` — sets failed status with error message
- Both XML and Claude extraction paths return `list[dict]` — no type branching in FTS or downstream steps

#### `search_service.py` ✅
Engine. NLP query → PostgreSQL FTS + field-level filters on `document_extractions`. `get_known_field_names()` tells Claude what's available. `translate_query()` returns structured filters. `run_search()` executes with numeric guard before CAST to prevent crashes on non-numeric values.

#### `agent_tools.py` ✅
Engine. Six read-only tool functions callable by the Claude agent: `search_documents`, `get_entity`, `query_extractions`, `get_transactions`, `get_findings`, `get_leads`. All workspace-scoped — `workspace_id` is injected by `execute()`, never passed by Claude. `execute()` dispatches by tool name and returns `{"error": "..."}` on failure. Results are size-capped (≤10 docs, ≤50 rows) to prevent context overflow. Extended per vertical via `agent_tools_<vertical>.py` pattern.

#### `agent_registry.py` ✅
Engine. Tool JSON schemas and vertical → tool list registry. `build_tool_schemas()` returns the 6 core tool schemas with their descriptions (design artifacts — Claude uses them to decide which tool to call). `get_tools_for_vertical(vertical)` returns the correct tool set, falling back to core tools for unregistered verticals. To add vertical-specific tools: extend `VERTICAL_TOOLS[vertical]`.

#### `ai_engine.py` ✅
Engine. Native Anthropic tool-use agentic loop. `chat()` runs up to 10 rounds: calls Claude with tool schemas, dispatches `tool_use` blocks via `agent_tools.execute()`, appends `tool_result` blocks, repeats until `end_turn`. On max rounds: `_synthesis_pass()` forces a final answer with tools disabled. `_extract_text()` extracts the first text block with fallback. `get_conversation_history()` fetches last 20 messages. Logs every tool call with name, params, result size, and latency. `build_workspace_context()` removed — Claude queries data via tools instead of reading a static dump.

#### `connectors/` 🔲
Engine. Phase 2 — public data sources feed into the pipeline.
```
app/services/connectors/
    irs_teos.py       (wraps scripts/fetch_990_xml.py)
    ohio_sos.py
    county_auditor.py
    building_permits.py
```

#### `signal_engine.py` 🔲
Engine framework. Phase 2 — evaluates signal rules from `signal_rules` table against `document_extractions`. The framework is engine. The rules it runs are vertical cap content.

#### `connectors/` + `search_service.py` + `ai_engine.py` = Intelligence Layer
The engine's intelligence layer. Understands documents, answers questions, surfaces connections. No domain knowledge — the same search and chat infrastructure serves every vertical. The questions differ; the mechanism is identical.

---

### API Routers (`backend/app/routers/`)

| Router | Endpoints | Layer | Status |
|---|---|---|---|
| `auth.py` | POST /auth/register, /auth/login | Engine | ✅ |
| `workspaces.py` | CRUD /workspaces | Engine | ✅ |
| `entities.py` | CRUD /entities, /relationships | Engine | ✅ |
| `findings.py` | GET /signal-types, CRUD /findings | Engine (model) + Fraud cap (signal seed data) | ✅ |
| `transactions.py` | CRUD /transactions | Engine | ✅ |
| `leads.py` | CRUD /leads | Engine | ✅ |
| `notes.py` | CRUD /notes | Engine | ✅ |
| `documents.py` | POST /documents, GET list/detail/extractions | Engine | ✅ |
| `search.py` | POST /workspaces/{id}/search/ | Engine | ✅ |
| `ai.py` | POST + GET /conversations, POST /conversations/{id}/messages | Engine | ✅ |
| `connectors.py` | POST /connectors/{source} | Engine | 🔲 Phase 2 |

---

### Schema Registry (`document_schemas` table)

All 11 schemas are `vertical = "general"` — available in every workspace regardless of vertical. The schema describes how to extract fields from a document type. What to DO with those fields is vertical cap logic.

| Schema | Fields | XML parse? | Available to |
|---|---|---|---|
| PARCEL-RECORD | 370 | No | All verticals |
| DEED | 64 | No | All verticals |
| 990 | 235 | **Yes** | All verticals |
| SOS-FILING | 47 | No | All verticals |
| UCC | 52 | No | All verticals |
| BUILDING-PERMIT | 13 | No | All verticals |
| AUDIT-REPORT | 122 | No | All verticals |
| SCREENSHOT | 26 | No | All verticals |
| OBITUARY | 63 | No | All verticals |
| PLAT | 51 | No | All verticals |
| CORRESPONDENCE | 59 | No | All verticals |

**Future vertical-specific schemas** get `vertical = "insurance"`, `vertical = "legal"`, etc. and only activate in matching workspaces.

---

### Seeds (`backend/app/seeds/document_schemas.py`)
**Layer:** Engine  
**How to run:** `docker-compose exec backend python -m app.seeds.document_schemas`  
**To add a schema:** Add `seed_X_schema(db)` following existing pattern, add to `main()`.  
**Status:** ✅ Connected

---

## FRAUD CAP COMPONENTS

These components contain fraud-specific domain knowledge. They do not ship with other verticals.

### Signal Type Seed Data
**Currently lives in:** `backend/app/routers/findings.py` (`SIGNAL_TYPES_SEED` constant)  
**What it is:** 8 fraud-specific signal type definitions (SR-003, SR-004, SR-005, SR-015, SR-021, SR-024, SR-025, SR-026)  
**Should move to (Phase 3):** `app/caps/fraud/signal_types.py` — the fraud cap installer  
**Status:** ⚠️ MISPLACED — currently in the engine layer, should be in the fraud cap

### SR Signal Definitions (full catalog)
**Currently:** Documented in memory files and roadmap, not yet in code  
**Phase 2:** Signal rule definitions go into `signal_rules` table (Phase 2B framework)  
**Phase 3:** Fraud cap installer seeds all SR rules via `signal_rules` table  
**Status:** 🔲 Planned

### Network Graph
**What it is:** Visual map of entity relationships, property chains, UCC lien networks — built from fraud-specific relationship data. The fraud cap defines what a meaningful connection looks like. A different vertical builds a different graph with different logic.  
**Engine provides:** `entities`, `relationships`, `transactions` tables  
**Fraud cap provides:** Graph rendering logic, which connections to surface, what layout means  
**Status:** 🔲 Planned (Phase 3 — fraud cap)

### Investigation Timeline
**What it is:** Chronological view of fraud-relevant events. Fraud cap selects which extracted date fields matter and what sequence reveals. Engine stores the dates; cap decides what to show.  
**Status:** 🔲 Planned (Phase 3 — fraud cap)

### Investigation Workflow Config
**What it is:** The sequence an investigation follows — upload → extract → signals → findings → network graph → timeline → referral  
**Phase 3:** Fraud cap defines this workflow. Insurance cap defines a different one.  
**Status:** 🔲 Planned

### Referral Package Export
**What it is:** AG/IRS/FBI complaint format generators  
**Phase 3:** Fraud cap only — insurance cap has its own export format  
**Status:** 🔲 Planned

---

## Infrastructure

### Docker + docker-compose ✅
Layer: Engine. `docker-compose up -d` starts full stack.

### Alembic Migrations
**Migrations in order:**
1. `5a4ff7266708_initial_schema` — creates all 17 tables, FTS index, audit trigger
2. `c12f44824c55_add_no_schema_status_and_extraction_error` — adds `no_schema` to extraction_status enum, adds `extraction_error` column to documents table
3. `a3b8e1f92d44_add_is_deleted_to_documents` — adds `is_deleted` and `deleted_at` columns to documents table (soft-delete compliance)

A clean `alembic upgrade head` produces the correct full schema.  
**Status:** ✅ Connected

### FTS Index + Audit Trigger ✅
Applied via SQL in Task 2. GIN index on `documents.search_vector`. PostgreSQL trigger on `audit_log`.

---

## Test Coverage

| Test file | Layer | Passing |
|---|---|---|
| `test_auth.py` | Engine | ✅ 5/5 |
| `test_workspaces.py` | Engine | ✅ 5/5 |
| `test_entities.py` | Engine | ✅ 3/3 |
| `test_findings.py` | Engine + Fraud cap | ✅ 3/3 |
| `test_transactions.py` | Engine | ✅ 2/2 |
| `test_leads.py` | Engine | ✅ 2/2 |
| `test_notes.py` | Engine | ✅ 2/2 |
| `test_documents.py` | Engine | ✅ 5/5 |
| `test_extractions.py` | Engine | ✅ 2/2 |
| `test_agent_tools.py` | Engine | ✅ 27/27 |
| `test_ai.py` (updated) | Engine | ✅ 8/8 |
| **Total** | | **67/67** |

---

## Phase Integration Map — Where Loose Ends Land

```
ENGINE LOOSE ENDS:
scripts/fetch_990_xml.py
    → Phase 2: app/services/connectors/irs_teos.py
    → Phase 2: POST /workspaces/{id}/connectors/irs-teos

Alembic migration (no_schema + extraction_error)
    → Phase 2 prerequisite: write migration before Phase 2 starts

Signal detection framework
    → Phase 2: app/services/signal_engine.py
    → Phase 2: signal_rules table

FRAUD CAP LOOSE ENDS:
Signal type seed data (currently in findings router)
    → Phase 3: app/caps/fraud/signal_types.py

Full SR signal rule definitions
    → Phase 3: seeded via signal_rules table by fraud cap installer

Investigation workflow + referral export
    → Phase 3: fraud cap only
```

---

## Update Log

| Date | What changed |
|---|---|
| 2026-05-19 | Initial inventory created. Tasks 1-8 complete. 29/29 tests. |
| 2026-05-19 | 11 document schemas seeded. fetch_990_xml.py and parse_990_xml.py built. |
| 2026-05-20 | Restructured engine vs. fraud cap separation. All 11 schemas changed to vertical=general. Signal type seed data flagged as misplaced in engine layer. Roadmap rewritten with IDP-first architecture. |
| 2026-05-20 | Pipeline hardening: (1) get_schema_for_type now vertical-aware — prefers vertical-specific, falls back to general. (2) XML and Claude extraction paths both return list[dict] — no type branching. (3) Alembic migration c12f44824c55 written and applied — no_schema enum + extraction_error column. All three flagged issues resolved. 29/29 tests. |
| 2026-05-20 | Task 9 complete. NLP search: translate_query → run_search with FTS + field filters. Numeric guard prevents CAST crashes. 32/32 tests. |
| 2026-05-20 | Task 10 complete. AI chat: build_workspace_context + Claude + conversation history. 35/35 tests. |
| 2026-05-20 | Live demo hardening: 3 bugs fixed — (1) Claude wraps JSON in markdown fences, strip before parsing. (2) Claude uses field/value keys instead of field_name/field_value, save_extractions accepts both. (3) max_tokens=2000 truncates 64-field extractions, raised to 4096. Real deed: 41 fields extracted, NLP search and AI chat both confirmed working. |
| 2026-05-26 | Tool-use chat agent. Added agent_tools.py (6 tools + dispatcher), agent_registry.py (schemas + vertical registry). Rewrote ai_engine.py with native Anthropic tool-use loop — 10-round cap, synthesis pass, per-call logging, is_error flag on failures. Added migration a3b8e1f92d44 (is_deleted on documents). Router fix: message save timing. 67/67 tests. |
