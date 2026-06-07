# Phase 2F — Commercial Readiness + Connector Foundation Design

**Date:** 2026-05-31
**Phase:** 2F — pre-Phase 3. Last engine work before vertical packaging.
**Status:** Approved for implementation

---

## Purpose

Two things must land before the first vertical cap:

1. **Commercial readiness** — three cost/metering changes that make the platform affordable to run at customer volume.
2. **Connector foundation** — the framework that lets the engine pull documents from public data sources, plus its first live connector (IRS TEOS), a Sources UI, an AI suggestion path, and a digital viewer for sourced files that have no PDF.

The connector foundation is the centerpiece. It directly answers a failure from the prior project (Catalyst): connectors that worked but had no home in the UI. The fix is to design the *whole path* — search, confirm, select, pull, view — not just the fetch. Get the foundation right and every future connector (Ohio SOS, county auditor, building permits) drops into it as cap content in Phase 3.

Everything here is **engine-level**. No domain knowledge. Each connector self-declares which verticals it serves; the engine surfaces the right ones per workspace.

---

## Vocabulary

- **Workspace** — the engine term for the case/claim/matter container. All UI copy uses "workspace." The cap rebrand (Phase 3) relabels it per vertical. Never write "case" in engine code or copy.
- **Connector** — a self-describing module that fetches documents from one public source. Like a skill: declares its id, name, description, verticals, and parameters; implements `search()` and `fetch()`.
- **Connector run** — one pull operation. Persisted as a `ConnectorRun` row: what was searched, what landed, status.
- **Sourced document** — a `Document` whose `source` is a connector id (not `"upload"`). Carries provenance.
- **Digital document view** — a rendered, dark-theme view of a structured document (no PDF), laid out from extracted fields.

---

## Part A — Commercial Readiness

Three independent backend changes. No external dependencies. Can ship as the first PR of the phase.

### A1. Prompt caching

In `extraction_engine.py` `_extract_batch`, the schema field-description block is identical across every document of a given type. Wrap it in an Anthropic `cache_control: {type: "ephemeral"}` block so the first call writes cache and subsequent calls read it. 60–90% input-token reduction on extraction. See the `claude-api` skill for the exact block placement.

Acceptance: cache-write on first call, cache-read on second call for the same schema, verifiable via `usage.cache_creation_input_tokens` / `usage.cache_read_input_tokens` in the response, logged to `claude_call_logs`.

### A2. Model routing by task

Add two constants to `claude_client.py`:

```python
EXTRACTION_MODEL = "claude-haiku-4-5-20251001"  # structured extraction on clean docs
CHAT_MODEL = "claude-sonnet-4-6"                  # reasoning across many docs
```

- `extraction_engine.py` field batches use `EXTRACTION_MODEL`.
- `ai_engine.py` uses `CHAT_MODEL`.
- **Type detection stays on Sonnet** — ambiguous documents need the stronger model.

No other behavior changes. Existing tests that patch the client still pass; assert the model arg where a test cares.

### A3. Usage metering foundation

New service `app/services/metering.py`, one function:

```python
def get_workspace_usage(workspace_id, billing_period_start, db) -> dict:
    """Sum tokens and count documents processed for a workspace in a billing period.
    Reads claude_call_logs. Data layer only — Phase 4A builds enforcement + UI on top."""
```

Returns `{input_tokens, output_tokens, total_tokens, documents_processed, period_start}`. No new table — `claude_call_logs` already has per-call token counts and timestamps. No endpoint in this phase; the query + its tests are the deliverable.

---

## Part B — Connector Framework

The foundation. Parallels `agent_registry.py` / `agent_tools.py` but for data sources.

### B1. `ConnectorBase` — the two-phase contract

`app/services/connectors/base.py`. Abstract base every connector implements.

**Metadata (class attributes):**
- `id: str` — machine key (`"irs-teos"`)
- `name: str` — display name (`"IRS TEOS — 990 Filings"`)
- `description: str` — what it fetches and why it helps
- `verticals: list[str]` — `["general"]` = all workspaces; `["fraud"]` = fraud only
- `search_schema: dict` — JSON Schema for search input (e.g. `{query: str}`)

**Methods:**

```python
def search(self, params: dict) -> list[SearchCandidate]:
    """Phase 1. Search the source by human-friendly terms (name).
    Returns candidates with enough identifying detail for the operator to pick:
    display_name, identifiers (EIN, address), location, and an opaque `ref`
    the connector uses to list/fetch."""

def list_items(self, candidate_ref: str) -> list[FetchableItem]:
    """Phase 2. Given a chosen candidate, list what is available to pull —
    each with year/date, item type (e.g. '990' vs '990-EZ'), and an opaque
    `item_ref`. Lets the operator checkbox exactly what they want."""

def fetch(self, item_refs: list[str], workspace_id, db) -> FetchResult:
    """Phase 3. Fetch the selected items as files and hand each to the
    existing pipeline. Returns per-item outcome: created | skipped (dedup) | failed."""
```

`SearchCandidate`, `FetchableItem`, `FetchResult` are small dataclasses/Pydantic models in `base.py`.

**Why two phases (search → list → fetch):** Every public-records source works this way — you don't start with the ID, you start with a name. Searching first and surfacing candidates with full name + location + identifier is the exact gap the prior project missed. Splitting `list_items` from `search` keeps each step cheap and lets the operator confirm the org *before* enumerating filings.

**`fetch` hands to the existing pipeline — no second ingestion path.** For each item: get bytes → `document_pipeline.create_pending_document()` → `process_upload_background()`. A 990 XML hits `parse_strategy="xml_direct"` and extracts at full confidence automatically. The connector never parses or extracts — it only acquires bytes and tags provenance.

### B2. `connector_registry.py`

Parallels `agent_registry.py`. Imports all connector classes, registers by `id`.

```python
def get_connectors_for_vertical(vertical: str) -> list[ConnectorBase]
def get_connector(connector_id: str) -> ConnectorBase | None
```

`get_connectors_for_vertical` returns connectors whose `verticals` includes the workspace vertical or `"general"`. Adding a connector in Phase 3 is: write the class, register it. No router or UI change.

### B3. `ConnectorRun` model + migration

`app/models/connector_run.py`. One row per pull.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `workspace_id` | FK workspaces | |
| `connector_id` | str | machine key — connectors live in code, not a table |
| `search_query` | str | human terms entered (`"Bright Future"`) |
| `candidate_label` | str | resolved org (`"Bright Future Ministries Inc · EIN 12-3456789"`) |
| `params` | JSONB | full structured selection (candidate_ref, item_refs) |
| `status` | str | `running` / `complete` / `failed` |
| `result` | JSONB | per-item outcomes: `[{item, status: created/skipped/failed, document_id?, reason?}]` |
| `error_message` | str nullable | run-level failure |
| `started_at` / `completed_at` | datetime | |

Soft-delete columns (`is_deleted`/`deleted_at`) for consistency with other models. No FK to a connector table.

Migration adds `connector_runs`. Also adds provenance columns to `documents` (see B4).

### B4. Document provenance

Add to `documents`:
- `source: str NOT NULL DEFAULT 'upload'` — `"upload"` or a connector id
- `source_ref: UUID nullable` — the `ConnectorRun.id` that produced it

Set in `create_pending_document()` (add optional `source` / `source_ref` params, default to upload so existing callers are unchanged). Written to the immutable audit log on creation: `action="document_sourced"` for connector pulls, with connector id, search query, and resolved candidate.

**Dedup is automatic via the existing SHA-256 hash.** The pipeline already hashes first. If a fetched file's hash matches an existing non-deleted document in the workspace, `fetch` records that item as `skipped` (reason: already in workspace) and creates no new row. Reported in the run result, never silent.

### B5. Endpoints — `app/routers/connectors.py`

All under `get_current_user` + `get_workspace_or_404`.

```
GET  /workspaces/{id}/connectors
     → connectors available for this workspace's vertical (metadata + search_schema)

POST /workspaces/{id}/connectors/{connector_id}/search
     Body: { ...search params }  → list[SearchCandidate]

POST /workspaces/{id}/connectors/{connector_id}/list
     Body: { candidate_ref }     → list[FetchableItem]

POST /workspaces/{id}/connectors/{connector_id}/fetch
     Body: { candidate_ref, candidate_label, search_query, item_refs }
     → creates ConnectorRun (status=running), runs fetch() in BackgroundTasks,
       returns { run_id, status: "running" }

GET  /workspaces/{id}/connector-runs?page&limit       → paginated history, newest first
GET  /workspaces/{id}/connector-runs/{run_id}         → single run status (poll target)
```

`search` and `list` are synchronous (fast, read-only against the external source). `fetch` is async — same `BackgroundTasks` pattern as document upload. The frontend polls `connector-runs/{run_id}` every 3s until terminal status (no SSE needed for this).

Routers stay thin: validate → call connector via registry → persist run → return. Fetch orchestration (loop items, dedup, pipeline handoff, result assembly) lives in a `connector_service.py` so the router doesn't hold business logic.

---

## Part C — IRS TEOS Connector (the one live connector this phase)

`app/services/connectors/irs_teos.py` implements `ConnectorBase`. `id="irs-teos"`, `verticals=["general"]`.

Wraps the existing `scripts/fetch_990_xml.py` logic (HTTP-range ZIP reads, index CSV scan). That script is keyed by EIN; this connector adds the **search-by-name** layer in front.

- `search({query})` → searches the IRS index by organization name, returns candidates: `display_name`, `EIN`, city/state, `ref=EIN`. (If the IRS bulk index lacks name search, the connector builds a name→EIN lookup from the yearly index CSVs it already downloads; document the chosen mechanism in the implementation.)
- `list_items(ein)` → returns the filings available for that EIN across years: `{year, form_type (990/990-EZ), filed_date, item_ref}`.
- `fetch(item_refs, ...)` → downloads each selected XML, saves to `UPLOAD_DIR`, hands to the pipeline with `source="irs-teos"`. 990 XML extracts at full confidence with no Claude call.

**Why IRS TEOS only:** existing logic, known API, clean XML format. Ohio SOS, county auditor, building permits require external-API research (rate limits, auth, response shapes) and are unknown until contacted — they ship in Phase 3 as fraud-cap connectors (`verticals=["fraud"]`), declared against this same framework. The framework is ready for them; only `search`/`list_items`/`fetch` need implementing.

---

## Part D — Sources UI

New workspace section. Engine-level — shows in every workspace.

### D1. Nav

Add **Sources** to `WorkspaceSidebar.jsx` engine items, positioned between Documents and Search. Always shown (engine item). Route `.../sources`.

### D2. Sources page — `pages/workspace/Sources.jsx`

Two panels.

**Left — connector workflow (search engine, not a query form):**
1. Connector picker + search box. Operator types a name (`"Bright Future"`), hits Search. No identifier required.
2. **Results:** candidate list. Each shows full legal name, city/state, and identifier (EIN). Operator selects the right one by sight (radio). *This is the step the prior project missed.*
3. **Available items:** once a candidate is selected, list fetchable items with checkboxes — year, form type, filed date. Multi-select, not all-or-nothing. "Select all" + "Pull N into workspace."
4. Submitting calls `/fetch`, creates a run, moves focus to history.

Phase 3 connectors appear as disabled preview cards with a vertical badge ("Fraud · Phase 3") so the framework's reach is visible before those connectors exist.

**Right — pull history:**
`ConnectorRun` rows, newest first. Each: connector name, resolved candidate + query, status pill (running w/ spinner / complete / failed), document count, timestamp. Running rows poll `connector-runs/{run_id}` every 3s. Completed rows link to the documents that landed. Per-item outcomes (created / skipped-dedup / failed) shown on expand.

### D3. Workspace render-mode preference

Add `document_render_mode: str` to workspaces (`"schema"` default | `"faithful"`). Set at workspace creation (add to the creation modal in `WorkspacesHome.jsx`) and editable in workspace settings. Drives the digital viewer renderer selection (Part E). Migration adds the column, default `"schema"`.

### D4. API client — `frontend/src/api/connectors.js`

`listConnectors`, `searchConnector`, `listConnectorItems`, `fetchConnector`, `listRuns`, `getRun`.

---

## Part E — Digital Document Viewer

Sourced structured files (990 XML) have no PDF. The DocumentViewer's left pane is built around a PDF blob — it would render empty. Fix: make the **left renderer pluggable**; the shell (split pane, right-side extracted-fields panel) is unchanged.

### E1. Renderer selection

`DocumentViewer.jsx` chooses the left-pane renderer:

```
has a PDF/image file?  → PdfRenderer (existing react-pdf path)
else (structured/sourced) → DigitalDocumentRenderer
```

Right pane (extracted fields) is identical for both.

### E2. `DigitalDocumentRenderer.jsx` + renderer registry

Engine ships **one generic, schema-driven renderer.** It reads `schema.schema_fields` + the document's extractions, groups fields by the existing `group` key (from the review-pane work), and renders dark-theme sections — a polished data sheet in the shape of the document. Works for *any* structured document with zero per-type code.

A **renderer registry** (parallels the connector registry) lets a cap register a faithful per-type template:

```js
// engine
registerRenderer("__default__", DigitalDocumentRenderer)
getRenderer(docType, renderMode)
  → if renderMode === "faithful" and a template is registered for docType → that template
  → else → DigitalDocumentRenderer (generic)
```

- **Engine (this phase):** generic renderer + registry mechanism + the workspace `document_render_mode` toggle (D3).
- **Cap (Phase 3):** faithful templates (`Form990View.jsx`, etc.) register themselves. The engine never contains the 990 template — only the fraud vertical cares about 990s.

**Why both, with the toggle:** an investigator builds muscle memory of how a document *looks*; rearranging it hinders their workflow. So a vertical can opt into faithful, document-shaped rendering. But the engine must render *anything* structured out of the box, so the generic renderer is the always-present fallback — a doc type with no faithful template still renders, never breaks.

---

## Part F — AI Suggestion Path

The differentiator: Claude notices a missing source and tells the operator where to look — but never fetches on its own.

### F1. `suggest_source` agent tool

Add one **read-only** tool to `agent_tools.py`, registered in the core set in `agent_registry.py` (all verticals).

```python
suggest_source(connector_id, search_query, reason) -> structured suggestion
```

It **does not fetch.** It returns a suggestion object: which connector, what *search* to run (a name/query — not a pre-filled identifier the model might get wrong), and why it helps. Aligns with the search-first flow: Claude proposes "search Bright Future in IRS TEOS," the operator runs it and picks the real result. The agent stays within the existing read-only trust boundary.

### F2. Chat action card

The chat frontend renders a `suggest_source` result as an action card in the thread: connector name, the suggested search, the reason, and a "Run this search" button. Clicking it deep-links to the Sources page with the connector + query pre-filled, dropping the operator at the results step. The operator confirms the candidate and selects items exactly as in the manual flow — one code path, one trust boundary. A "Dismiss" button discards the card.

---

## Data Model Summary

**New table:** `connector_runs` (B3).
**New columns on `documents`:** `source`, `source_ref` (B4).
**New column on `workspaces`:** `document_render_mode` (D3).
**Migration:** one revision adding all three.

---

## File Map

**Create — backend:**
- `app/services/connectors/__init__.py`
- `app/services/connectors/base.py` — `ConnectorBase`, `SearchCandidate`, `FetchableItem`, `FetchResult`
- `app/services/connectors/irs_teos.py` — IRS TEOS connector
- `app/services/connector_registry.py`
- `app/services/connector_service.py` — fetch orchestration (loop, dedup, pipeline handoff, result assembly)
- `app/services/metering.py` — `get_workspace_usage`
- `app/models/connector_run.py`
- `app/routers/connectors.py`
- `app/schemas/connector.py` — Pydantic request/response models
- migration `*_phase2f_connectors_provenance_render_mode.py`
- `tests/test_connectors.py`, `tests/test_connector_irs_teos.py`, `tests/test_metering.py`

**Create — frontend:**
- `pages/workspace/Sources.jsx`
- `components/documents/DigitalDocumentRenderer.jsx`
- `components/documents/rendererRegistry.js`
- `api/connectors.js`
- tests: `test_sources.jsx`, `test_digital_renderer.jsx`

**Modify — backend:**
- `app/services/extraction_engine.py` — prompt caching (A1), `EXTRACTION_MODEL` (A2)
- `app/services/claude_client.py` — `EXTRACTION_MODEL` / `CHAT_MODEL` constants (A2)
- `app/services/ai_engine.py` — use `CHAT_MODEL` (A2)
- `app/services/document_pipeline.py` — `source` / `source_ref` params on `create_pending_document`
- `app/services/agent_tools.py` — `suggest_source` tool (F1)
- `app/services/agent_registry.py` — register `suggest_source`
- `app/models/document.py`, `app/models/workspace.py` — new columns
- `app/schemas/document.py` — expose `source`, `source_ref`
- `app/main.py` — register connectors router

**Modify — frontend:**
- `components/layout/WorkspaceSidebar.jsx` — Sources nav item
- `pages/workspace/DocumentViewer.jsx` — pluggable left renderer
- `pages/workspace/AIChat.jsx` — render `suggest_source` action card
- `pages/WorkspacesHome.jsx` — `document_render_mode` in creation modal
- `components/documents/DocumentList.jsx` — source badge on sourced docs

---

## Testing

**Backend:**
- `test_connectors.py` — registry vertical filtering; search/list/fetch endpoint contracts (connector mocked); `ConnectorRun` lifecycle running→complete; dedup path records `skipped` and creates no document; audit log entry on sourced doc.
- `test_connector_irs_teos.py` — search-by-name returns candidates with EIN; `list_items` returns filings; `fetch` hands bytes to pipeline with `source="irs-teos"` (network mocked).
- `test_metering.py` — `get_workspace_usage` sums tokens and counts documents for a period from `claude_call_logs`.
- Extend `test_pipeline.py` — `create_pending_document` sets provenance; default `source="upload"` unchanged.
- Caching/model routing — assert model arg and cache_control block presence where the client is patched.

**Frontend:**
- `test_sources.jsx` — search → results → select candidate → checkbox items → pull; history row polls and resolves.
- `test_digital_renderer.jsx` — generic renderer groups fields by `group`; registry returns faithful template when `renderMode="faithful"` and one is registered, else falls back to generic.

---

## What This Spec Does Not Cover (Phase 3 / later)

- **Ohio SOS, county auditor, building-permit connectors** — Phase 3 fraud-cap content; built against this framework.
- **Faithful per-type renderers** (`Form990View`, etc.) — Phase 3 cap content; the registry + toggle ship now.
- **Scheduled / watched pulls** (annual re-check of an EIN) — Phase 3+ once a cap wants it.
- **Usage enforcement + customer-facing usage UI** — Phase 4A, on top of `get_workspace_usage`.
- **Vertical UI rebrand** (workspace → case/claim labels) — separate Phase 3 task.

---

## Build Sequence (for the implementation plan)

1. **Part A** (commercial readiness) — independent, smallest, ship first.
2. **B3/B4 migration + models** (connector_runs, provenance, render_mode) — data layer before logic.
3. **B1/B2 framework** (`ConnectorBase`, registry) — TDD against a fake connector.
4. **Part C** (IRS TEOS) — first real connector against the framework.
5. **B5 + connector_service** (endpoints + fetch orchestration + dedup).
6. **Part D** (Sources UI) — search→pick→select→pull + history.
7. **Part E** (digital viewer + renderer registry).
8. **Part F** (suggest_source tool + chat action card).
