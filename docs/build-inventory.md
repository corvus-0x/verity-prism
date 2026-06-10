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
Engine. A workspace is a case/claim/matter container — vertical-agnostic. WorkspaceMember tracks access. The `vertical` field on Workspace tells the signal engine which cap to apply. `document_render_mode` (`"schema"` | `"faithful"`) controls how sourced documents display in DocumentViewer — `schema` uses the generic grouped renderer; `faithful` uses a per-type template if registered. Defaults to `"schema"`.

#### `document.py` ✅
Engine. One row per uploaded file. `extraction_status` (`pending`/`complete`/`failed`/`no_schema`), `extraction_error`. Hash, OCR text, search vector. No domain knowledge.

#### `document_schema.py` ✅
Engine. The schema registry. `vertical = "general"` means available in all workspaces. `vertical = "fraud"` activates only in fraud workspaces. `vertical = "insurance"` activates only in insurance workspaces. 10 schemas are `general`; OBITUARY is `vertical = "fraud"`.

New fields: `parse_strategy` enum (`claude` | `xml_direct`) — tells the pipeline how to extract this document type without hardcoding type strings. `default_confidence_threshold` float — per-schema baseline for the extraction evaluator (Phase 2A). Both set in the model and in all seeds.

#### `document_extraction.py` ✅
Engine. **The central IDP table.** One row per extracted field per document. No domain knowledge — just field_name, field_value, field_type, confidence, attempt. Every vertical's signals query this table.

`attempt` column: 1 = initial Claude extraction, 2 = automated retry (evaluator pass), 3 = human correction (review UI). All rows are kept — history is never deleted. `list_extractions` returns the latest attempt per field_name by default; `?include_history=true` returns all rows.

#### `claude_call_log.py` ✅
Engine. Observability sink for every Claude call in the extraction pipeline. One row per API call: call_type (`type_detection` | `extraction_batch` | `extraction_retry`), document_id, workspace_id, schema_id, model, attempt, latency_ms, input_tokens, output_tokens, success, error_message. No FK constraints — log rows survive document soft-deletes. Written via isolated SessionLocal so logging failures never affect extraction transactions.

#### `connector_run.py` ✅
Engine. One row per connector pull. `connector_id` (machine key), `search_query` + `candidate_label` (what was searched), `params` (candidate_ref + item_refs), `status` (running/complete/failed), `result` (JSONB per-item outcomes), `error_message`, timestamps, soft-delete. No FK to a connector table — connectors live in code. Pull history for the Sources UI. Documents gain `source_ref` = the ConnectorRun id that produced them (`source_type="api_pull"`).

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
Engine. JWT creation/verification, bcrypt hashing. `get_current_user` dependency accepts both `Authorization: Bearer` header and `access_token` httpOnly cookie (Bearer first, cookie fallback — backward compat for tests, browser uses cookie).

#### `ocr.py` ✅
Engine. Text extraction from PDFs and images. PyMuPDF for embedded text, pytesseract for scanned pages. Entry point: `extract_text(file_bytes, file_type)`.

#### `extraction_engine.py` ✅
Engine. Three functions:
- `detect_document_type(ocr_text, db)` — loads known types from `document_schemas` at call time (no hardcoded list); adding a schema row immediately makes that type detectable
- `get_schema_for_type(doc_type, db, workspace_vertical)` — vertical-aware schema lookup. Prefers vertical-specific schema; falls back to `general`. A fraud workspace gets fraud schemas first, then general.
- `extract_fields()` + `save_extractions()` — Claude extracts fields per schema definition, returns `list[dict]`

`ExtractionBatchError` (Phase 3 C2 fix): raised by `_extract_batch` on API failure — distinct from a legitimate empty result. `extract_fields` re-raises if all batches fail. Callers get an explicit signal instead of silent `[]`.

`TEXT_LIMIT = 200_000` (Phase 3 H5 fix): extraction batches send up to 200k chars of OCR text (≈50k tokens). Old cap was 4000 chars, which silently dropped evidence from multi-page documents. Warning logged when a document exceeds the limit.

#### `naming.py` ✅
Engine. Generates standardized filenames: `YYYY-MM-DD_DOC-TYPE_ENTITY_DESCRIPTION.ext`. Loads known doc types from `document_schemas` table at call time — no hardcoded type list.

#### `xml_parser.py` ✅
Engine. Direct XML parse for structured files. Reads field values from element paths in schema descriptions. Returns `list[dict]` — same format as `extract_fields()`. The pipeline calls `save_extractions()` identically for both paths. Confidence = 1.0. `is_valid_xml_bytes()` validates raw bytes (type-agnostic). Activated when `schema.parse_strategy == "xml_direct"`.

#### `document_pipeline.py` ✅
Engine. Orchestrates the full upload pipeline:
- `create_pending_document()` — hash + store + pending record (before HTTP response)
- `process_upload_background()` — OCR → type → **vertical-aware** schema lookup → extract → FTS → audit (after response via BackgroundTasks)
- Pipeline reads `schema.parse_strategy` to route XML vs Claude — no hardcoded type strings
- `_no_schema()` — creates investigation lead for unknown document types
- `_fail()` — sets failed status, deletes stored file (Phase 3 L3 fix: no orphans on disk after failure), writes audit log
- Both XML and Claude extraction paths return `list[dict]` — no type branching in FTS or downstream steps

Phase 3 C2 defence-in-depth guard: if `schema.parse_strategy == "claude"` and schema has defined fields but `raw_extractions` is empty, pipeline calls `_fail` instead of silently marking `complete`.

#### `search_service.py` ✅
Engine. NLP query → PostgreSQL FTS + field-level filters on `document_extractions`. `get_known_field_names()` tells Claude what's available. `translate_query()` returns structured filters. `run_search()` executes with numeric guard before CAST to prevent crashes on non-numeric values. Both FTS and field-filter branches filter `Document.is_deleted == False` (Phase 4 H1 fix).

#### `export_service.py` ✅
Engine. All export and SSE logic extracted from the documents router (Phase 5 M5). Five functions: `latest_extractions(document_id, db)` — latest attempt per field via subquery; `build_document_csv/json(doc, extractions)` — per-document serializers with OWASP formula-injection protection; `build_workspace_csv/json(docs, db)` — workspace-level serializers. `document_status_stream(workspace_id, document_id)` — async generator that opens its own `SessionLocal`, yields SSE `data: {...}\n\n` lines, closes on terminal status or 5-min timeout.

#### `claude_client.py` ✅
Engine. Lazy singleton Anthropic client (Phase 5 L6). `get_client()` constructs `Anthropic(api_key=...)` on first call. All four Claude-using services call `claude_client.get_client()` instead of instantiating at import time. Single patch target in tests: `patch("app.services.claude_client.get_client", return_value=mock_client)`. Phase 2F: defines `EXTRACTION_MODEL` (Haiku 4.5) and `CHAT_MODEL` (Sonnet 4.6) — model routing by task, single source of truth.

#### `metering.py` ✅
Engine. `get_workspace_usage(workspace_id, billing_period_start, db)` — read-only aggregation over `claude_call_logs`: sums input/output tokens and counts distinct documents processed for a workspace since the period start. No table, no endpoint — the data layer Phase 4A tier enforcement + usage display build on (Phase 2F A3).

#### `embedding_service.py` ✅
Engine. Document-level vector embeddings for semantic search. `embed_document()` builds a text representation from extracted fields ("Type: DEED | grantor_name: ... | ..."), generates a 1536-dim vector via OpenAI `text-embedding-3-small`, stores it on `documents.embedding` (pgvector). Runs as pipeline step 8.5; never fails a document. Configured via `settings.openai_api_key` — optional, search degrades to keyword-only FTS when unset. `search_service.semantic_search()` queries by cosine distance; `run_search()` merges keyword + semantic results in `hybrid` mode (default), or runs either alone via `mode="keyword"` / `mode="semantic"`.

#### `agent_tools.py` ✅
Engine. Seven read-only tool functions callable by the Claude agent: `search_documents`, `get_entity`, `query_extractions`, `get_transactions`, `get_findings`, `get_leads`, `suggest_source`. All workspace-scoped — `workspace_id` is injected by `execute()`, never passed by Claude. `execute()` dispatches by tool name and returns `{"error": "..."}` on failure. Results are size-capped (≤10 docs, ≤50 rows) to prevent context overflow. `suggest_source` returns a structured dict (`action/connector_id/search_query/reason`) — read-only, never fetches. Extended per vertical via `agent_tools_<vertical>.py` pattern.

#### `agent_registry.py` ✅
Engine. Tool JSON schemas and vertical → tool list registry. `build_tool_schemas()` returns the 7 core tool schemas with their descriptions (design artifacts — Claude uses them to decide which tool to call). `get_tools_for_vertical(vertical)` returns the correct tool set, falling back to core tools for unregistered verticals. To add vertical-specific tools: extend `VERTICAL_TOOLS[vertical]`.

#### `ai_engine.py` ✅
Engine. Native Anthropic tool-use agentic loop. `chat()` runs up to 10 rounds: calls Claude with tool schemas, dispatches `tool_use` blocks via `agent_tools.execute()`, appends `tool_result` blocks, repeats until `end_turn`. On max rounds: `_synthesis_pass()` forces a final answer with tools disabled. `_extract_text()` extracts the first text block with fallback. `get_conversation_history()` fetches last 20 messages. Logs every tool call with name, params, result size, and latency. `build_workspace_context()` removed — Claude queries data via tools instead of reading a static dump.

#### `extraction_evaluator.py` ✅
Engine. Two functions:
- `evaluate(extractions, threshold)` — pure function, no DB. Compares each field's confidence against the schema threshold, returns `EvaluationResult(low_confidence_fields, threshold_used, total_fields)`.
- `run_retry(document_id, workspace_id, ocr_text, schema, low_confidence_field_names, db)` — builds a mini-batch of only the failing fields, calls `_extract_batch()`, saves results as `attempt=2` rows. Called by the pipeline between save_extractions() and filename generation. Catches `ExtractionBatchError` from `_extract_batch` — retry failure is non-fatal and returns `[]` without failing the document.

#### `connectors/` ✅ (irs_teos) | 🔲 (others — Phase 3 cap)
Engine. Public data sources feed into the pipeline. Three-phase contract in `connectors/base.py` — `ConnectorBase`: `search(params)` → `SearchCandidate`s, `list_items(candidate_ref)` → `FetchableItem`s, `fetch(item_refs, workspace_id, user_id, db)` → `FetchResult`. `fetch` hands bytes to the existing pipeline with provenance; it never parses/extracts.
```text
app/services/connectors/
    base.py             ✅  ConnectorBase + SearchCandidate/FetchableItem/FetchItemResult/FetchResult
    irs_teos.py         ✅  IrsTeosConnector — search-by-name over IRS index CSVs, EIN-keyed fetch
    ohio_sos.py         🔲  Phase 3 (fraud cap)
    county_auditor.py   🔲  Phase 3 (fraud cap)
    building_permits.py 🔲  Phase 3 (fraud cap)
```

#### `connector_registry.py` ✅
Engine. Parallels `agent_registry.py`. `get_connectors_for_vertical(vertical)` returns connectors serving that vertical or `general`; `get_connector(id)` returns one. Connectors live in code, registered in `_REGISTRY`. Adding a connector in Phase 3 = write the class, register it — no router/UI change.

#### `connector_service.py` ✅
Engine. `ingest_bytes(...)` hands fetched bytes to `document_pipeline` with provenance (`source_type="api_pull"`), deduping by SHA-256 (`find_existing_by_hash`) — a hash collision in the workspace returns `skipped`, no duplicate evidence row. `run_fetch(run_id, connector_id, item_refs, workspace_id, user_id)` is the BackgroundTasks orchestrator — opens its own `SessionLocal`, runs the connector's `fetch`, finalizes the `ConnectorRun` row.

#### `signal_engine.py` 🔲
Engine framework. Phase 2 — evaluates signal rules from `signal_rules` table against `document_extractions`. The framework is engine. The rules it runs are vertical cap content.

#### `connectors/` + `search_service.py` + `ai_engine.py` = Intelligence Layer
The engine's intelligence layer. Understands documents, answers questions, surfaces connections. No domain knowledge — the same search and chat infrastructure serves every vertical. The questions differ; the mechanism is identical.

---

### API Routers (`backend/app/routers/`)

| Router | Endpoints | Layer | Status |
|---|---|---|---|
| `auth.py` | POST /auth/register, /auth/login (sets httpOnly cookie + returns user), POST /auth/logout, GET /auth/me | Engine | ✅ |
| `workspaces.py` | CRUD /workspaces | Engine | ✅ |
| `entities.py` | CRUD /entities, /relationships | Engine | ✅ |
| `findings.py` | GET /signal-types, CRUD /findings | Engine (model) + Fraud cap (signal seed data) | ✅ |
| `transactions.py` | CRUD /transactions | Engine | ✅ |
| `leads.py` | CRUD /leads | Engine | ✅ |
| `notes.py` | CRUD /notes | Engine | ✅ |
| `documents.py` | POST /documents, GET list/detail/extractions/file | Engine | ✅ |
| `search.py` | POST /workspaces/{id}/search/ | Engine | ✅ |
| `ai.py` | POST + GET /conversations, POST /conversations/{id}/messages | Engine | ✅ |
| `schemas.py` | GET /schemas/ | Engine | ✅ |
| `review.py` | GET /workspaces/{id}/review-queue, PATCH /documents/{id}/extractions/{id}/correct | Engine | ✅ |
| `documents.py` | GET /documents/{id}/extractions.csv, /extractions.json — per-document export | Engine | ✅ |
| `documents.py` | GET /documents/{id}/status/stream — SSE for real-time status | Engine | ✅ |
| `workspaces.py` | GET /workspaces/{id}/extractions.csv, /extractions.json — workspace-level export | Engine | ✅ |
| `audit.py` | GET /workspaces/{id}/audit-log?page&limit | Engine | ✅ |
| `connectors.py` | GET /workspaces/{id}/connectors, POST .../connectors/{id}/search, .../list, .../fetch, GET .../connector-runs[/{run_id}] | Engine | ✅ |

---

### Schema Registry (`document_schemas` table)

All 11 schemas are `vertical = "general"` — available in every workspace regardless of vertical. The schema describes how to extract fields from a document type. What to DO with those fields is vertical cap logic.

| Schema | Fields | parse_strategy | Available to |
|---|---|---|---|
| PARCEL-RECORD | 370 | claude | All verticals |
| DEED | 64 | claude | All verticals |
| 990 | 235 | **xml_direct** | All verticals |
| SOS-FILING | 47 | claude | All verticals |
| UCC | 52 | claude | All verticals |
| BUILDING-PERMIT | 13 | claude | All verticals |
| AUDIT-REPORT | 122 | claude | All verticals |
| SCREENSHOT | 26 | claude | All verticals |
| OBITUARY | 63 | claude | **Fraud vertical only** |
| PLAT | 51 | claude | All verticals |
| CORRESPONDENCE | 59 | claude | All verticals |

**Adding a new document type** requires only a new row in `document_schemas` — no code changes. Set `parse_strategy="xml_direct"` for structured XML types, `"claude"` for everything else.

**Future vertical-specific schemas** get `vertical = "insurance"`, `vertical = "legal"`, etc. and only activate in matching workspaces.

---

### Seeds (`backend/app/seeds/document_schemas.py`)
**Layer:** Engine  
**How to run:** `docker-compose exec backend python -m app.seeds.document_schemas`  
**To add a schema:** Add `seed_X_schema(db)` following existing pattern, add to `main()`.  
**Upsert behavior:** All seed functions now UPDATE existing records (fields + extraction_prompt) if the schema already exists. Re-running the seed safely updates a live DB — no need to drop and recreate.  
**Cleanliness rule:** Field descriptions and extraction prompts must contain no case-specific content — no real names, org names, county names, or signal codes. Use generic examples only.  
**Status:** ✅ Connected

---

### Frontend (`frontend/src/`)

#### Context

| File | What it does | Status |
|---|---|---|
| `context/WorkspaceContext.jsx` | Fetches workspace once at layout level, provides to all children via context. Eliminates redundant per-component fetches. `useWorkspace()` hook for consumers. | ✅ |

#### Layout Components

| File | What it does | Status |
|---|---|---|
| `components/layout/AppShell.jsx` | Global shell — header with logo (links to /workspaces), "Schema Library" nav link, plain-English search bar, sign-out. | ✅ |
| `components/layout/WorkspaceSidebar.jsx` | Vertical-aware nav. Engine items always shown: Overview, Documents, Sources, Search, Entities, AI Chat. Cap items shown only when `workspace.vertical` matches: Fraud → Transactions, Findings, Leads. `VERTICAL_SECTIONS` map — adding a new vertical's nav is one entry. | ✅ |

#### Pages — Platform Level

| File | Route | What it does | Status |
|---|---|---|---|
| `pages/Login.jsx` | `/login` | JWT login form | ✅ |
| `pages/WorkspacesHome.jsx` | `/workspaces` | Workspace list + creation modal. Modal captures name and vertical (General / Fraud Investigation / Insurance). Defaults to General. No more `prompt()`. | ✅ |
| `pages/SchemaLibrary.jsx` | `/schemas` | Platform-level Schema Library. All active schemas from DB grouped by vertical. Each card shows display name, document type key, field count, parse strategy, confidence threshold. Expandable field list: name, type, description, required flag. | ✅ |

#### Pages — Workspace Level

| File | Route | What it does | Status |
|---|---|---|---|
| `pages/workspace/WorkspaceLayout.jsx` | `/workspaces/:id` | Wraps workspace in `WorkspaceProvider`. Renders AppShell + WorkspaceSidebar + page outlet. | ✅ |
| `pages/workspace/Overview.jsx` | `/workspaces/:id` | Summary stats. Reads vertical from context — General shows Documents + Entities; Fraud adds Findings. Grid adapts to card count. | ✅ |
| `pages/workspace/Documents.jsx` | `.../documents` | Document list + upload dropzone. Clicking a document navigates to DocumentViewer. No inline extraction panel. | ✅ |
| `components/documents/DocumentList.jsx` | — | Shared document list used by Documents and DocumentViewer. Cards are Links; selected card highlighted. | ✅ |
| `pages/workspace/Search.jsx` | `.../search` | Plain-English search | ✅ |
| `pages/workspace/Entities.jsx` | `.../entities` | Entity list and detail | ✅ |
| `pages/workspace/AIChat.jsx` | `.../chat` | AI chat interface | ✅ |
| `pages/workspace/Transactions.jsx` | `.../transactions` | Fraud cap only — financial transactions | ✅ |
| `pages/workspace/Findings.jsx` | `.../findings` | Fraud cap only — signal findings | ✅ |
| `pages/workspace/Leads.jsx` | `.../leads` | Fraud cap only — investigation leads | ✅ |
| `pages/workspace/DocumentViewer.jsx` | `.../documents/:id` | Split-pane PDF viewer (65%) + extracted fields panel (35%). react-pdf renders in-browser, no plugin needed. Status-aware fields panel surfaces extraction_error on failure. | ✅ |
| `pages/workspace/ExtractionReview.jsx` | `.../review` | Review queue for `needs_review` documents. Table shows filename, doc type, low-confidence field count. Review button opens DocumentViewer with `?review=1`. | ✅ |
| `pages/workspace/AuditLog.jsx` | `.../audit` | Chronological audit log: timeline with colored dots, client-side search + action filter, pagination (50/page, Previous/Next). Subtitle: "Every action on every document is tamper-proof." | ✅ |
| `pages/workspace/Sources.jsx` | `.../sources` | Three-phase connector flow: connector picker + name search → candidate list with EIN → filing checklist + pull button. Pull history panel on the right. Reads `?connector=&query=` deep-link params for AI-initiated searches. | ✅ |

#### Hooks + Global UI (`frontend/src/hooks/`, `frontend/src/components/shared/`)

#### `components/documents/DigitalDocumentRenderer.jsx` ✅
Engine. Schema-driven dark-theme renderer for sourced (non-PDF) documents. Groups `schema_fields` by their `group` key into labeled sections. Displays each field's extracted value from the `extractions` array; shows `—` for missing values. Used by DocumentViewer's left pane when `source_type !== "upload"` and no physical file is stored.

#### `components/documents/rendererRegistry.js` ✅
Engine. Renderer plugin registry. `getRenderer(docType, renderMode)` returns the appropriate React component: `"schema"` mode always returns `DigitalDocumentRenderer`; `"faithful"` mode returns a registered per-type template if available, otherwise falls back to `DigitalDocumentRenderer`. Vertical caps register faithful templates via `registerRenderer(docType, Component)`.

#### `components/sources/SuggestSourceCard.jsx` ✅
Engine. Chat action card for `suggest_source` tool results. Displays connector ID, search query, and Claude's reasoning. "Run this search" button deep-links to Sources with `?connector=&query=` prefilled. "Dismiss" removes the card from the thread. Rendered by AIChat when a message content parses as `{action: "suggest_source", ...}`.

#### `hooks/useToast.js` + `components/shared/ToastContainer.jsx` ✅
Engine. Global toast notification system. `ToastProvider` mounts at app root in `main.jsx`. Four variants: success (green), error (red), info (blue), warning (orange). Bottom-right position, title+message, 4s auto-dismiss, max 3 visible, timer cleanup on unmount, ARIA live region.

#### `hooks/useExtractionStream.js` ✅
Engine. SSE stream consumer for extraction status. fetch+ReadableStream with `credentials: 'include'` (httpOnly cookie auth). `reader` variable lifted to outer useEffect scope — `reader?.cancel()` called on unmount so connections don't linger (Phase 6 L2 fix). Closes on terminal status (complete/failed/no_schema/needs_review). Exponential backoff reconnect: base 1s, doubles each retry, cap 32s, max 5 retries.

---

#### API Clients (`frontend/src/api/`)

| File | Calls | Status |
|---|---|---|
| `auth.js` | POST /auth/login, /auth/register, /auth/logout; GET /auth/me | ✅ |
| `workspaces.js` | CRUD /workspaces | ✅ |
| `documents.js` | POST + GET /documents, getDocumentFile | ✅ |
| `entities.js` | CRUD /entities | ✅ |
| `findings.js` | CRUD /findings | ✅ |
| `transactions.js` | CRUD /transactions | ✅ |
| `leads.js` | CRUD /leads | ✅ |
| `notes.js` | CRUD /notes | ✅ |
| `search.js` | POST /search | ✅ |
| `ai.js` | POST + GET /conversations | ✅ |
| `schemas.js` | GET /schemas/ | ✅ |
| `connectors.js` | GET /connectors, POST .../search, .../list, .../fetch, GET .../connector-runs[/{id}] | ✅ |

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
4. `d4e9f2a83b17_add_parse_strategy_to_document_schemas` — adds `parse_strategy` enum (`claude`|`xml_direct`) and `default_confidence_threshold` float to `document_schemas`; sets 990 to `xml_direct`/`1.0`
5. `c8dd75f9d15c_schema_cleanup_obituary_and_sr_` — moves OBITUARY to `vertical='fraud'`; strips SR signal codes from extraction_prompts; cleans fraud investigation commentary from 5 field descriptions
6. `e1f3a2b94c07_add_attempt_needs_review_and_call_log` — adds `attempt` column (INTEGER NOT NULL DEFAULT 1) to `document_extractions`; adds `needs_review` to `extraction_status` enum; creates `claude_call_logs` table with indexes on `document_id` and `called_at`
7. `3f29a7ad2392_add_audit_log_immutable_trigger` — PostgreSQL trigger `BEFORE UPDATE OR DELETE ON audit_log` that raises EXCEPTION; enforces the immutability guarantee documented in CLAUDE.md (Phase 2 C1 fix)
8. `a1b2c3d4e5f6_phase4_search_integrity_soft_delete` — changes `documents.search_vector` from TEXT to TSVECTOR with GIN index; adds `is_deleted`/`deleted_at` to `transactions`, `findings`, `investigation_leads`, `notes`, `relationships` (Phase 4 H2 + L5 fix)
9. `b7e72d2_connector_runs_and_source_ref` — adds `connector_runs` table; adds `source_type`/`source_ref` columns to `documents` (Phase 2F Plan 2)
10. `50f2b84a06aa_phase2f_workspace_render_mode` — adds `document_render_mode` column to `workspaces` (Phase 2F Plan 3)

A clean `alembic upgrade head` produces the correct full schema.  
**Status:** ✅ Connected

### FTS Index + Audit Trigger ✅
Applied via SQL in Task 2. GIN index on `documents.search_vector`. PostgreSQL trigger on `audit_log`.

---

## Test Coverage

Counts verified by `pytest --collect-only` on 2026-06-10 (evals/ excluded — require live API key).

| Test file | Layer | Passing |
|---|---|---|
| `test_agent_tools.py` | Engine | ✅ 29 |
| `test_ai.py` | Engine | ✅ 10 |
| `test_audit.py` | Engine | ✅ 6 |
| `test_audit_immutability.py` | Engine | ✅ 3 |
| `test_auth.py` | Engine | ✅ 10 |
| `test_claude_client.py` | Engine | ✅ 5 |
| `test_config.py` | Engine | ✅ 4 |
| `test_connector_base.py` | Engine | ✅ 2 |
| `test_connector_irs_teos.py` | Engine | ✅ 4 |
| `test_connector_registry.py` | Engine | ✅ 2 |
| `test_connector_service.py` | Engine | ✅ 2 |
| `test_connectors_api.py` | Engine | ✅ 3 |
| `test_deps.py` | Engine | ✅ 3 |
| `test_documents.py` | Engine | ✅ 16 |
| `test_embedding_service.py` | Engine | ✅ 5 |
| `test_entities.py` | Engine | ✅ 3 |
| `test_export_service.py` | Engine | ✅ 7 |
| `test_extraction_caching.py` | Engine | ✅ 3 |
| `test_extraction_engine.py` | Engine | ✅ 2 |
| `test_extractions.py` | Engine | ✅ 10 |
| `test_field_validator.py` | Engine | ✅ 8 |
| `test_findings.py` | Engine + Fraud cap | ✅ 3 |
| `test_leads.py` | Engine | ✅ 2 |
| `test_metering.py` | Engine | ✅ 2 |
| `test_normalization.py` | Engine | ✅ 19 |
| `test_notes.py` | Engine | ✅ 2 |
| `test_observability.py` | Engine | ✅ 5 |
| `test_pipeline.py` | Engine | ✅ 18 |
| `test_review.py` | Engine | ✅ 4 |
| `test_sanitize.py` | Engine | ✅ 7 |
| `test_schema_review.py` | Engine | ✅ 6 |
| `test_search.py` | Engine | ✅ 12 |
| `test_transactions.py` | Engine | ✅ 2 |
| `test_workspaces.py` | Engine | ✅ 7 |
| **Backend total** | | **226/226** |
| **Frontend total** (9 files) | | **18/18** |
| **Grand total** | | **244/244** |

---

## Phase Integration Map — Where Loose Ends Land

```
ENGINE LOOSE ENDS:
SCREENSHOT schema misclassification (identified 2026-06-01 validation run)
    Problem: Land record screenshots (county auditor, parcel data) are being
    classified as SCREENSHOT and evaluated against a social-media-oriented schema
    (post_text, author_name, likes_count, comment fields). These fields are absent,
    confidence ~0.1, which was (before the evaluator fix) tanking automation rate.
    The evaluator fix helps but the root cause remains: type detection can't
    distinguish social media screenshots from property record screenshots.
    Fix options:
      A) Improve detect_document_type prompt to differentiate screenshot subtypes
      B) Add PROPERTY-SCREENSHOT schema variant for land record screenshots
      C) Simplify SCREENSHOT schema to only contain universally present fields
    → Phase 3 candidate: review during fraud cap schema packaging

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
| 2026-05-26 (evening) | Core hardening + IDP expansion architecture. Core: CORS config, file size limit, soft-delete on list_documents, workspace null guard. Expansion: parse_strategy + default_confidence_threshold on DocumentSchema (migrations d4e9f2a + c8dd75f); detect_document_type and generate_standardized_name load types from DB; pipeline routes on schema.parse_strategy; is_parseable_xml removed. Schema cleanup: OBITUARY → vertical=fraud; SR signal codes and fraud commentary removed from 9 general schemas. 75/75 tests. |
| 2026-05-28 | Frontend vertical separation: WorkspaceContext; vertical-aware sidebar and overview; workspace creation modal with vertical picker. Schema Library: GET /schemas/ endpoint, SchemaLibrary page, AppShell nav link, schemas API client, vite proxy. Full schema cleanup: all case-specific content removed from all 11 schemas in seed file and live DB; seed functions converted to upserts. Frontend inventory section added. Roadmap updated with document viewer (Phase 2A next), extraction review UI, Engine UI section (real-time status, export, audit log), multi-user in Phase 4A. |
| 2026-05-28 | Document viewer complete (Phase 2A). GET /documents/{id}/file endpoint. DocumentList extracted. DocumentViewer with react-pdf (10.x), 65/35 split, status-aware fields panel, blob URL lifecycle management. 80/80 tests. Known gap: GET /documents/{id} does not filter is_deleted — pre-existing, fix deferred. Blog post 008 written (post-008-the-source.md). |
| 2026-05-28 | Phase 2A complete. extraction_evaluator.py (evaluate + run_retry), claude_call_log.py model, review.py router (GET review-queue + PATCH correct), ExtractionReview.jsx, ExtractionTable editable mode, DocumentViewer review mode (?review=1). list_extractions returns latest-attempt-per-field by default. Migration e1f3a2b94c07: attempt column, needs_review enum, claude_call_logs table. ADRs added to docs/decisions/. 80/80 tests. |
| 2026-05-28 | Phase 2C complete. Toast system (useToast + ToastContainer, timer cleanup, ARIA). Document status pill badges (needs_review/no_schema/failed added to Badge.jsx). SSE real-time extraction status (StreamingResponse + useExtractionStream with exponential backoff). Data export: 4 endpoints (per-doc + workspace CSV/JSON) + ⋯ context menu frontend. Audit log: paginated backend + timeline UI with search/filter. 85/85 tests. |
| 2026-05-29 | Phase 2C cleanup + CI hardening. Ruff UP017 + import sorting (54 fixes, 19 files). ESLint JSX parserOptions. useToast.js → useToast.jsx. CI: DATABASE_URL added, evals/ excluded (require live API key). CodeRabbit caught missing nextId ref (critical — ReferenceError on every toast). test_documents.jsx wrapped with ToastProvider. pyproject.toml: requires-python >=3.11. ADR-0004 written (SSE over polling, fetch+ReadableStream for Bearer auth). Blog post-009 written. 82/82 CI tests. |
| 2026-05-29 | Phase 3 code audit remediation (PR #5). C2: `ExtractionBatchError` — `_extract_batch` raises on API failure instead of returning `[]`; `extract_fields` re-raises if all batches fail; pipeline-level guard prevents silent `complete` on empty claude extraction. H5: `TEXT_LIMIT = 200_000` — OCR text cap raised from 4000 to 200k chars, full document evidence now reaches Claude. L3: `_fail` deletes stored file on pipeline failure, no orphans on disk. H4: `test_pipeline.py` — 9 tests (evaluator unit, happy-path, C2 failure, H5 truncation, L3 cleanup) written TDD-style. 118/118 tests. |
| 2026-05-30 | Phase 4 code audit remediation (audit phases 4–6, PR #6 + #7). Phase 4: H1 — soft-delete filters in `run_search` and `query_extractions`; H2 — `search_vector` migrated TEXT→TSVECTOR + GIN index (migration `a1b2c3d4e5f6`); L1 — `get_conversation_history` workspace-scoped; L5 — `is_deleted`/`deleted_at` on Transaction, Finding, Lead, Note, Relationship. Phase 5: M5 — `get_workspace_or_404` moved to `app/deps.py`; export+SSE logic extracted to `export_service.py`; four `Anthropic()` module-level clients consolidated into `claude_client.py` lazy singleton. Phase 6: M6 — httpOnly cookie auth (`/login` sets cookie, `/logout`, `/me`; hybrid Bearer+cookie in `get_current_user`; frontend removes localStorage, adds `AuthInit`, `withCredentials: true`); M7 — `AIChat.handleSend` catch+rollback+toast, `WorkspaceContext` silent catch; L2 — SSE reader cancelled on unmount; L4 — 401 interceptor uses `NavigatorSetter` router navigation. 136/136 tests (123 backend + 13 frontend). All 2026-05-29 audit findings resolved. |
| 2026-05-31 | Phase 2F Plan 1 — Commercial readiness (branch `feat/phase2f-commercial-readiness`). `EXTRACTION_MODEL`/`CHAT_MODEL` constants in `claude_client.py`; field extraction routed to Haiku 4.5, type detection + chat stay on Sonnet. Prompt caching: `_extract_batch` splits the prompt into a cacheable ephemeral static block + uncached document block (60-90% input-token cut). `metering.py` — `get_workspace_usage` query over `claude_call_logs` (Phase 4A billing data layer). 137 backend passed, 1 skipped. |
| 2026-05-31 | Phase 2F Plan 3 complete — Sources UI + digital viewer + AI suggestion. Backend: `document_render_mode` on workspaces (migration 50f2b84a06aa); `suggest_source` as 7th agent tool (read-only, returns structured suggestion). Frontend: `connectors.js` API client; `Sources.jsx` (connector search → pick → filing list → pull + history); `DigitalDocumentRenderer.jsx` (schema-driven grouped renderer for sourced docs); `rendererRegistry.js` (plugin registry, cap-extendable); `SuggestSourceCard.jsx` (AI action card with deep-link); DocumentViewer left pane now pluggable (digital renderer for non-PDF sourced docs); DocumentList shows source badge. 18 frontend tests + 187 backend tests (186 pass, 1 pre-existing GIN index test). |
| 2026-06-10 | Portfolio hardening (TDD, branch `feat/portfolio-hardening`). Search correctness: field-filter intersection now constrains the document query BEFORE the 50-doc window (was: limit-first silently dropped matches past the FTS scan window); `matched_fields` uses latest-attempt-per-field via `export_service.latest_extractions` (corrections supersede stale values). Extraction: `max_tokens` cap 4096→8192 (full 40-field batch needs 4200); explicit None-check fallback preserves legitimately-empty `''` values. Evaluator regression tests added for the null/empty-value skip (absent fields no longer flag needs_review). Config: `openai_api_key` moved into `Settings`; LangSmith key read from settings; hardcoded `claude-sonnet-4-6` strings in `detect_document_type`/`translate_query` replaced with `CHAT_MODEL` constant. Hygiene: ruff now lints `backend/tests` in CI (31 autofixes + E402 per-file-ignore); test fixtures use neutral identities. `embedding_service` documented in inventory. Test table re-verified by collect-only: 226 backend + 18 frontend = 244. |
