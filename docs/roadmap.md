# Verity Prism — Product Roadmap

**Last updated:** 2026-05-29  
**Core principle:** Verity Prism is an Intelligent Document Processing platform first. Verticals are plug-and-play caps that tell the platform what to care about. The engine ships to every customer. The cap ships only to the relevant vertical.

---

## The Architecture in One Picture

```
┌─────────────────────────────────────────────────────────┐
│                    VERITY PRISM ENGINE                    │
│                                                           │
│  Any document in → structured data out                    │
│                                                           │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────┐ │
│  │  Ingestion   │  │  Extraction  │  │  Intelligence  │ │
│  │  Pipeline    │  │  Engine      │  │  Layer         │ │
│  │              │  │              │  │                │ │
│  │  hash        │  │  OCR         │  │  NLP search    │ │
│  │  store       │  │  type detect │  │  AI chat       │ │
│  │  index       │  │  field parse │  │                │ │
│  └──────────────┘  └──────────────┘  └────────────────┘ │
│                                                           │
│  ┌──────────────────────────────────────────────────┐   │
│  │  Data Connectors (public sources → pipeline)      │   │
│  │  IRS TEOS | SOS | County Auditor | Permits | ...  │   │
│  └──────────────────────────────────────────────────┘   │
│                                                           │
│  ┌──────────────────────────────────────────────────┐   │
│  │  Schema Registry (plug-and-play, per document type│   │
│  │  DEED | 990 | UCC | PARCEL | PERMIT | FORM | ...  │   │
│  └──────────────────────────────────────────────────┘   │
│                                                           │
│  The engine knows nothing about fraud, insurance,         │
│  or any other domain. It processes documents.             │
└─────────────────────────────────────────────────────────┘
           │                    │                    │
           ▼                    ▼                    ▼
  ┌────────────────┐  ┌─────────────────┐  ┌──────────────────┐
  │  FRAUD CAP     │  │  INSURANCE CAP  │  │  [FUTURE CAP]    │
  │                │  │                 │  │                  │
  │  Fraud schemas │  │  Insurance      │  │  Legal discovery │
  │  SR signals    │  │  schemas        │  │  Compliance      │
  │  Network graph │  │  Claims signals │  │  Real estate     │
  │  Timeline      │  │  Claim workflow │  │  title           │
  │  Investigation │  │  Claims system  │  │  ...             │
  │  workflow      │  │  export         │  │                  │
  │  AG/IRS/FBI    │  │                 │  │                  │
  │  referral      │  │                 │  │                  │
  └────────────────┘  └─────────────────┘  └──────────────────┘

An insurance customer installs the engine + insurance cap.
They never see fraud signals, fraud schemas, or fraud workflows.
A fraud customer installs the engine + fraud cap.
Adding a new vertical = new cap. Engine unchanged.
```

---

## What a Vertical (Cap) Contains

Every vertical is a self-contained package:

| Component | What it is | Example: Fraud | Example: Insurance |
|---|---|---|---|
| **Schema set** | Which document types are active | DEED, 990, UCC, PARCEL, SOS, PERMIT, AUDIT | INSURANCE-FORM, ACORD, APPRAISAL, INVOICE |
| **Signal definitions** | What patterns to detect | SR-003 valuation anomaly, SR-025 false disclosure | Duplicate claim, inflated contractor invoice |
| **Workflow config** | What steps a case follows | Upload → investigate → findings → referral | Intake → extract → flag → adjuster review |
| **UI labels** | Terminology for the domain | "Case", "Finding", "Referral" | "Claim", "Discrepancy", "Adjustment" |
| **Export format** | How output leaves the system | AG/IRS/FBI complaint package | Claims system API, structured report |

Shared schemas (PARCEL-RECORD, for example) can belong to multiple verticals. The schema registry supports this — a schema tagged `general` is available to all verticals. A schema tagged `fraud` only activates in fraud workspaces.

---

## Phase 1 — IDP Engine Core
**What it is:** The document processing foundation. Every future phase and every future vertical runs on this.  
**Status:** ✅ COMPLETE

### Engine capabilities delivered in Phase 1
- Document ingestion: SHA-256 evidence lock → OCR → type detection → field extraction → FTS index
- Schema registry: 11 document type schemas, plug-and-play, no code change to add new types
- XML direct parse path: structured files (990 XML) bypass OCR, extracted at full confidence
- Background processing: upload returns immediately, pipeline runs async
- Fail-fast error handling: `failed` / `no_schema` statuses, auto-lead creation for unknown types
- Workspace management, entities, relationships, transactions, notes
- Audit log: immutable, PostgreSQL trigger-enforced
- NLP search: plain-English queries → FTS + field-level filters on `document_extractions`
- AI chat: native Anthropic tool-use agentic loop — 6 read-only tools, 10-round cap, synthesis pass, vertical tool registry
- React frontend: all 8 workspace sections working

### What Phase 1 does NOT include
- Any vertical-specific logic
- Public data connectors
- Signal detection
- Extraction evaluation / observability
- Multi-user collaboration

---

## Engine Core Hardening (between Phase 1 and Phase 2)
**What it is:** Non-negotiable fixes identified in principal dev review. The core must be locked down before any vertical work starts.  
**Status:** ✅ COMPLETE (2026-05-26)

### Completed
- `list_documents` now filters soft-deleted documents
- CORS origins moved to config (`CORS_ORIGINS` env var) — deployment-ready
- `get_workspace_or_404` raises 404 instead of silently returning None
- File size limit added to config (`MAX_UPLOAD_BYTES`, default 50 MB)
- Alembic verified on fresh database — all 5 migrations apply cleanly, head = `c8dd75f9d15c`
- `parse_strategy` and `default_confidence_threshold` on `DocumentSchema` — adding a new doc type is now a DB-only operation
- `KNOWN_DOCUMENT_TYPES` hardcoded list removed — `detect_document_type` and `generate_standardized_name` load types from DB at call time
- Pipeline routes on `schema.parse_strategy` not type strings — `is_parseable_xml` deleted
- All 11 seeds include `parse_strategy` and `default_confidence_threshold`; OBITUARY moved to `vertical="fraud"`
- SR signal codes and fraud investigation commentary removed from 9 general schema descriptions and extraction prompts
- **Frontend vertical separation** (2026-05-28): sidebar and overview now driven by `workspace.vertical` — General workspaces show engine-only nav; Fraud workspaces add Transactions/Findings/Leads. Workspace creation modal replaced `prompt()` with a proper form that captures name and vertical. `WorkspaceContext` provides workspace data to all children without redundant fetches.
- **Schema Library** (2026-05-28): platform-level page at `/schemas` showing all active document types grouped by vertical — field count, parse strategy, confidence threshold, and expandable full field list with name/type/description/required. Accessible from global header nav. Backend `GET /schemas/` endpoint added. All case-specific content (county names, person names, org names, signal codes) scrubbed from all 11 schemas in seed file and live DB. Seed functions now do upserts — re-running updates existing records.

### Deferred (not blocking Phase 2, but tracked)
- **Three Anthropic client instances** (`extraction_engine.py`, `search_service.py`, `ai_engine.py`) — consolidate into shared `app/services/claude_client.py` before adding retry logic or spend tracking
- **Signal type seed data in findings router** — move to cap installer before Insurance Vertical starts
- **Frontend test coverage** — Vitest suite exists in the plan but test count is not tracked; establish baseline before Phase 3

---

## Phase 2 — IDP Engine Capabilities
**What it is:** The engine gets smarter and more connected. No vertical logic — these capabilities serve all verticals equally.  
**Status:** In progress — 2A, 2C, and 2D complete. 2B (signal detection) moved to Phase 3. Remaining: 2E (data connectors).

### 2A — Intelligence Layer: Agentic Hardening + Document Viewer
The engine's intelligence layer is functional. These builds make it measurable and trustworthy, and give it a human interface for reviewing what it produces. **Must complete before connectors or signal detection** — connectors bring more documents; signal detection reads extracted fields. Both are only as good as extraction is reliable. Measure reliability first.

**Tool-use chat agent** ✅ DONE (2026-05-26):  
Replaced static context dump with native Anthropic tool-use loop. Claude calls 6 read-only tools to pull exactly what it needs. 10-round cap with synthesis pass fallback. Workspace-scoped dispatcher.

**Document viewer** ✅ DONE (2026-05-28):  
Split-pane view: PDF rendered in-browser (react-pdf, pdf.js bundled — no plugin required) on the left, extracted fields on the right. 65/35 split. Route-based navigation — each document has its own URL at `.../documents/:id`. Document list stays visible with selected doc highlighted. Status-aware fields panel: surfaces `extraction_error` text on failure, informative messages for pending/no_schema. File served from `GET /documents/{id}/file` behind JWT auth. Blob URL lifecycle managed to prevent memory leaks on navigation.  
*Spec:* `docs/superpowers/specs/2026-05-28-document-viewer-design.md`  
**Field-level linking deferred** — clicking a field to highlight its location in the PDF is the next pass after the extraction evaluator ships (requires text layer, built on existing react-pdf foundation).

**Extraction evaluation loop** ✅ DONE (2026-05-28):  
`extraction_evaluator.py` — pure `evaluate()` checks confidence against `schema.default_confidence_threshold`. `run_retry()` builds a mini-batch of only failing fields, calls Claude once more as `attempt=2`. If still below threshold after retry, document is flagged `needs_review`. XML-direct path skipped (always 1.0 confidence). Pipeline insertion: between `save_extractions()` and filename generation, gated on `schema.parse_strategy == "claude"`.

**Extraction review UI** ✅ DONE (2026-05-28):  
`ExtractionReview.jsx` at `/review` — queue of `needs_review` documents. Clicking Review opens `DocumentViewer?review=1`. Fields panel becomes editable: each row gets an Edit button, inline input, Accept/Cancel. Accepted corrections are saved as `attempt=3, confidence=1.0`. When all fields corrected, document status flips back to `complete`.

**Observability layer** ✅ DONE (2026-05-28):  
`claude_call_logs` table. Every extraction Claude call (type detection, field batches, retry batches) logged with call_type, latency_ms, input_tokens, output_tokens, model, success. Written via isolated `SessionLocal` — logging failure never affects extraction. Indexes on `document_id` and `called_at`.

### 2B — Signal Detection Framework
**Moved to Phase 3.** Signal rules are domain logic — every vertical has its own rule set with different operators, thresholds, and evidence patterns. Building a generic framework before two verticals exist means designing an abstraction for one use case. The fraud cap (Phase 3A) will define and build signal detection against fraud-specific field values. If insurance signals share enough structure, the common parts get extracted then — when we know what "common" actually means.

### 2C — Engine UI Completeness ✅ DONE (2026-05-28)
These are engine-level UI capabilities that any vertical needs. Not vertical-specific — they ship with the engine and are available in every workspace.

**Real-time extraction status** ✅ DONE:  
Server-sent events (SSE) on `GET /workspaces/{id}/documents/{doc_id}/status/stream` push `pending → processing → complete/failed` to the frontend in real time. `useExtractionStream` hook uses fetch+ReadableStream (not EventSource) for Bearer auth, exponential backoff reconnect (base 1s, cap 32s, max 5 retries).

**Data export** ✅ DONE:  
`GET /workspaces/{id}/documents/{doc_id}/extractions.csv` and `/extractions.json` — per-document field export. Workspace-level export: all extractions across all documents as a flat CSV. Formula injection protection (OWASP CSV-injection). ⋯ context menu on document cards; "Export all" workspace button.

**Audit log UI** ✅ DONE:  
Paginated `GET /audit-log?page&limit` endpoint. Timeline UI with colored action dots, client-side search + action filter, Previous/Next pagination. "Every action on every document is tamper-proof."

### 2D — Code Audit Remediation ✅ DONE (2026-05-30)
The code audit (conducted 2026-05-29 by Opus 4.8) identified security, data-integrity, and architecture findings across six remediation phases. All six phases are complete.

Full finding details and resolution notes in `docs/code-audit-2026-05-29.md`.

**Phase 4 ✅ — Search & soft-delete data integrity:**  
`run_search` and `query_extractions` now filter `Document.is_deleted`. `search_vector` migrated from `TEXT` to `TSVECTOR` with GIN index. Soft-delete columns (`is_deleted`/`deleted_at`) added to Transaction, Finding, Lead, Note, Relationship. `get_conversation_history` workspace-scoped.

**Phase 5 ✅ — Architecture refactor (thin routers, lazy client):**  
`get_workspace_or_404` moved to `app/deps.py`. Export/SSE logic extracted to `app/services/export_service.py`. Four module-level `Anthropic()` clients consolidated into lazy singleton `app/services/claude_client.py` — single patch target in tests.

**Phase 6 ✅ — Frontend resilience + JWT hardening:**  
`POST /auth/login` sets httpOnly, SameSite=Lax cookie; `GET /auth/me` restores session on page refresh; `POST /auth/logout` clears cookie. `get_current_user` accepts Bearer or cookie (hybrid — zero test changes). Frontend: no localStorage, `withCredentials: true`, `AuthInit` on startup, `ProtectedRoute` checks `user`. `AIChat.handleSend` rolls back optimistic message and shows toast on failure. SSE reader cancelled on unmount. 401 interceptor uses router navigation.

### 2E — Engine Quality + Observability
**Priority: get the engine measurably reliable before expanding it.** These items tell you whether extraction is actually working and give you the controls to improve it. Everything else — connectors, NL schema creation, vertical packaging — is only as good as the engine underneath.

**1. Dual confidence model** *(prerequisite — do before dashboard)*
Add `ocr_confidence` column to `document_extractions` alongside the existing `confidence` field (which is AI confidence). These diagnose different problems: low OCR confidence = bad scan quality; low AI confidence = ambiguous field definition in the schema. Right now Prism can't tell the difference. For text fields, OCR confidence = weakest word-level score. For table fields, OCR confidence = average across cells. The extraction engine populates both; the dashboard visualizes them as separate trends.

**2. Observability dashboard** *(do after dual confidence is in)*
Five dashboards confirmed from Hyland's own product. Each maps directly to data already in Prism's database — no new tables required for most of them.

| Dashboard | What it shows | Prism data source |
|---|---|---|
| Automation Rate Summary | % docs straight-through vs. human review vs. failed | `documents.status` counts |
| Inbound/Outbound Volume | Doc ingestion and completion volume over time | `documents.uploaded_at` / `completed_at` by day |
| Classification Details | Accuracy per schema, confidence trends, retry rates | `document_extractions` + `document_schemas` |
| Current System Processing | Real-time pipeline status — pending/processing counts | `documents` where status = pending/processing |
| Task Completion by User | Per-reviewer throughput and correction rate | Requires multi-user (Phase 4A) — defer |

**Automation Rate is the single most important metric.** It answers: what percentage of documents require no human intervention? Industry benchmark is 80%+. Every Phase 2E improvement should move this number up.

Confidence scores never surface to end users as raw numbers — they feed these dashboards and routing logic only.

**3. Dual confidence in the Review UI**
`ExtractionReview.jsx` currently shows a single confidence value per field. Once `ocr_confidence` is added to `document_extractions`, the review panel should display both — OCR confidence (scan quality) and AI confidence (extraction certainty) — so reviewers understand *why* a field was flagged, not just *that* it was flagged. Confirmed pattern from Hyland's own review UI.

**4. Three extraction types on schema fields**
Hyland defines three types: **Text** (OCR of written content), **Table** (grid data — columns defined at schema level, OCR confidence = average across cells), **Reasoning** (full document visual analysis — no OCR confidence). Prism's current `claude` parse strategy is effectively Reasoning mode for all fields. Add `extraction_type` per field in `schema_fields` JSON: `text | table | reasoning`. Tables need column definitions and different confidence math. This shapes how the extraction engine batches fields and how the dashboard buckets confidence scores.

**5. Two separate thresholds per field**
Hyland confirmed: there are two independent thresholds — **Field Review Threshold** (AI confidence) and **OCR Review Threshold** (scan quality confidence) — each configurable at both project level and per-field override. Prism currently has one threshold per schema. Update `schema_fields` JSON to support `ai_confidence_threshold` and `ocr_confidence_threshold` per field, both optional overrides of the schema-level defaults.

**6. Field validation rules — concrete types**
Add optional `validation` property to `schema_fields` JSON. Types confirmed from Hyland docs:
- `min_length` / `max_length` — character count bounds
- `regex` — pattern match (EIN format, email, currency)
- `required` — field must have a value; empty = flagged

Post-extraction, pre-signal. Catches semantic errors that Claude extracts confidently but incorrectly (transposed dates, wrong numeric format). Cross-field rules (deed_date before recording_date) are Phase 3 — they require knowing both field values simultaneously.

**7. Output format normalization** *(deferred — follow-on plan)*
New capability: a normalization layer applied to raw extracted values *before* they are stored. Configured per field in `schema_fields` JSON as an ordered list of transforms. Not implemented in Phase 2E — see Deferred section below. Types confirmed for the follow-on plan:
- `remove_chars` — strip symbols or punctuation (e.g., remove `#` from `#100`)
- `find_replace` — swap strings at runtime (normalize entity name variants)
- `date_format` — convert date to target format (e.g., `01.05.2026` → `05/01/2026`)
- `case` — upper / lower / sentence case
- `truncate` — trim N chars from left or right
- `format_number` — normalize currency, decimals, separators

This eliminates post-processing scripts in signal detection and downstream systems. A deed's `sale_amount` extracted as `$1,250,000.00` gets normalized to `1250000` before storage — signal detection compares numbers, not strings.

**8. Document flagging with structured reasons**
When a reviewer flags a document (not just corrects fields), they select a justification reason from a configured list and add a free-text note. The flag and note travel with the document through the rest of processing. Hyland defaults: "Unknown document type", "Document missing pages", "Low quality scan (illegible)". Prism equivalent: add `flag_reason` and `flag_note` columns to `documents`. The Classification Details dashboard shows rejection breakdown by reason — scan quality vs. wrong schema vs. missing pages. Turns unstructured rejections into queryable diagnostics.

**Deferred from this phase — must land before Phase 3:**
- *Full document review pane* — the core verification experience. Right pane maps over `schema.schema_fields` (not just extractions) — every defined field visible alongside the PDF, pre-populated where extracted, empty where not. Reviewer fills in or corrects any field. Replaces the current `ExtractionTable` review mode which only surfaces fields that exist in the DB. Requires a new endpoint for creating `attempt=3` rows on fields with no prior extraction row (insert, not patch). See build tracker deferred section for full design.
- *Partial batch retry* — when `batch_errors > 0` but `< len(batches)`, retry only the failed batches before flagging `needs_review`. Handles transient API errors silently. If retry also fails, route to the full review pane with empty fields visible. Currently partial failures complete silently with missing fields — no signal to investigator.

**Deferred from this phase — can wait:**
- *NL schema creation* — guided schema setup via plain English. Valuable for zero-training UX but not a quality prerequisite.
- *Extraction feedback loop* — feed human corrections back into future extraction prompts. Worth building once correction volume gives it signal.
- *Field-to-location highlighting* — click a field, highlight its position in the PDF. Already deferred from 2A; confirmed as standard by Hyland. Build when table extraction ships (requires text layer coordinates).
- *Parent/child schema inheritance* — e.g., DEED as parent class with WARRANTY_DEED, QUITCLAIM_DEED, SHERIFF_DEED as children inheriting base fields. Cleans up the schema registry. Phase 3 candidate when fraud cap schemas are packaged.
- *Field redaction* — overlay or burned redaction for PII fields (SSN, etc.). Phase 4 compliance feature.

### 2F — Data Connectors (pre-Phase 3)
Public data sources feed directly into the pipeline. Any vertical can use any connector.

**Architecture:** `app/services/connectors/` — each connector fetches data, converts to a file, hands to the pipeline. The connector doesn't know which vertical is using it.

```
app/services/connectors/
    irs_teos.py          ← 990 XML for any EIN
    ohio_sos.py          ← entity and UCC records
    county_auditor.py    ← parcel records by address/parcel number
    building_permits.py  ← permit history by address
```

**New endpoint pattern:**
```
POST /workspaces/{id}/connectors/irs-teos
POST /workspaces/{id}/connectors/ohio-sos
POST /workspaces/{id}/connectors/county-auditor
```

**Existing asset:** `scripts/fetch_990_xml.py` is the core IRS TEOS logic. 2E wraps it in the connector service.  
**Scheduled option:** Background job checks for new filings on watched EINs annually.  
**Cross-vertical use:** Fraud uses IRS TEOS for 990s. Insurance uses county auditor for property data. Same connector serves both.

---

## Phase 3 — Vertical Packaging
**What it is:** The engine gets its first two caps. Each vertical is a complete, installable package.  
**Trigger:** Phase 2A, 2C, and 2D complete. Engine extraction is measured, reliable, and security-hardened. At least one full end-to-end case has run against real documents with observable confidence metrics.

### 3A — Fraud Vertical v1.0
**Installs:** Fraud schema set + SR signal definitions + signal detection engine + investigation workflow + referral export
**Note:** Signal detection framework (originally Phase 2B) is built here, as fraud cap logic, not engine infrastructure.

**Schema set (already built, just needs vertical packaging):**
PARCEL-RECORD, DEED, 990, SOS-FILING, UCC, BUILDING-PERMIT, AUDIT-REPORT, SCREENSHOT, OBITUARY, PLAT, CORRESPONDENCE

**Signal definitions (SR-001 through SR-026):**
- SR-003 VALUATION_ANOMALY: sale_amount > 2x appraised_value_current
- SR-004 UCC_BURST: 3+ amendments to same financing statement within 15 minutes
- SR-005 ZERO_CONSIDERATION: conveyance_fee_exempt = true + seller_is_individual = true
- SR-015 DEED_TITLE_DEFECT: grantee_entity formed after deed execution date
- SR-021 REVENUE_SPIKE: total_revenue_cy > 5x prior year revenue
- SR-024 CHARITY_CONDUIT: building permit applicant = nonprofit, parcel owner = LLC
- SR-025 FALSE_DISCLOSURE: 990 gov_related_entity = false, deed shows same signatory on both entities
- SR-026 CONSTRUCTION_OVERAGE: permit estimated_value > total_revenue_cy same year
- *(full SR catalog in signal definitions)*

**Network graph:**
Visual map of entities, properties, transactions, and document links — built from fraud-specific relationship data. The fraud cap defines what a meaningful connection looks like (officer_of, controls, owns, financed_by). A different vertical would define a different graph with different edge types and different emphasis.

The engine stores entities and relationships. The fraud cap decides what to render and why.

**Investigation timeline:**
Chronological view of fraud-relevant events — deed recordings, 990 filing dates, UCC amendment timestamps, permit issuance dates, SOS filing events — ordered to reveal patterns. The fraud cap selects which date fields matter and what sequence means something. The engine provides the extracted dates.

**Investigation workflow:**
Upload → extract → signals fire → findings created → investigator reviews → network graph → timeline → referral package

**Referral export:**
- Ohio AG (Charitable Law Section) format
- IRS Form 13909 narrative
- FBI IC3 format
- Farm Credit Administration OIG

### 3B — Insurance Vertical v1.0
**Installs:** Insurance schema set + claims signal definitions + claim intake workflow + claims export

**Schema set (to be built when Phase 3 starts):**
INSURANCE-FORM, ACORD-FORM, PROPERTY-APPRAISAL, CONTRACTOR-INVOICE, MEDICAL-RECORD  
*Shared with fraud vertical:* PARCEL-RECORD (property data)

**Signal definitions:**
- Contractor invoice date after claim close date
- Estimated repair cost > property appraised value
- Duplicate claims across policies for same property
- *(defined when vertical is built)*

**Claim intake workflow:**
Upload forms → extract → flag discrepancies → adjuster review queue → decision

**Export:**
Claims system API push (integration TBD based on client system)  
Structured PDF report for manual review

**Contact:** Insurance vertical contact and pain point documented in private memory files.

---

## Phase 4 — Scale + Additional Verticals
**What it is:** Production infrastructure. The platform handles multiple clients, multiple verticals, at scale.  
**Trigger:** Phase 3 complete. First paying customer in each of two verticals.

### 4A — Multi-User and Organizations
Currently a single-account system. Phase 4A adds the user model needed for team sales and multiple clients.

- **Organizations** — a top-level tenant. Workspaces belong to an org, not a user.
- **User roles** — Admin (manage users, billing), Analyst (full workspace access), Viewer (read-only). Role-based access enforced at the API level.
- **Invitations** — invite by email, join an org, scoped to a vertical if needed.
- **Workspace isolation** — one org cannot see another org's workspaces, documents, or extracted data.

*Trigger:* First team sale. A single investigator or developer can use the platform without this. A firm with multiple analysts cannot.

### 4B — AWS Deployment
Docker Compose → AWS ECS/EKS. PostgreSQL → RDS. Files → S3. Background jobs → SQS. CDN for frontend.

### 4C — Additional Vertical Caps
Each new vertical is a schema set + signal definitions + workflow config + export format. The engine doesn't change.

**Candidates:**
- Legal discovery — contracts, depositions, court filings, privilege review
- Real estate title — chain of title analysis, lien searches, closing packages
- Compliance audit — board minutes, policy docs, governance review
- Nonprofit oversight — general 990 analysis beyond the fraud vertical

**Time to add a new vertical:** With the Phase 2 framework in place, a new vertical should take weeks, not months. Schema derivation (one session per document type, as established in Phase 1) + signal definitions + workflow config.

### 4D — Vertical Marketplace
Long-term: verticals become installable packages. A law firm buys the engine + legal cap. A title company buys the engine + real estate cap. An insurer buys the engine + insurance cap. They don't see each other's logic.

---

## Cross-Phase Principles

**The engine is the product. Verticals are configuration.**  
If you're changing the pipeline, the schema registry, the connector framework, or the search/AI layer — that's engine work. If you're adding signal rules, schemas for a domain, or export formats — that's vertical work. Keep them separate.

**Schemas are plug-and-play by design.**  
The `document_schemas` table already has a `vertical` field. A schema tagged `general` works in any workspace. A schema tagged `fraud` only activates in fraud workspaces. Insurance schemas tagged `insurance` never appear in a fraud case. No code change needed — just the row in the table.

**Every phase delivers working software.**  
Don't start Phase 3 until Phase 2D (audit hardening) and 2E (connectors) are complete. Signal detection is Phase 3A fraud cap work, not a Phase 2 prerequisite. Don't let verticals leak into engine phases.

**The build inventory stays current.**  
See `docs/build-inventory.md`. Everything built gets an entry. Every loose end gets a phase destination.

**The investigation case remains the engine's proving ground.**  
The fraud vertical was built first because it's the hardest case. If the engine handles it, it handles everything simpler. Every new engine capability gets validated against a fraud case before being generalized.

---

## Phase Completion Criteria

| Phase | Done when |
|---|---|
| Core Hardening | ✅ CORS configurable, file size bounded, soft-delete consistent, Alembic verified on fresh DB. |
| Phase 1 | ✅ All backend tasks pass. Frontend working. Documents flow through full pipeline end-to-end. |
| Phase 2 | 2A ✅ (document viewer, eval loop, observability). 2C ✅ (SSE status, export, audit log UI). 2D ✅ (all 6 audit phases — search integrity, thin routers, JWT hardening). 2B moved to Phase 3. Remaining: 2E (engine operability — NL schema creation, observability dashboard, per-field thresholds, field validation, feedback loop), 2F (data connectors — held until just before Phase 3). |
| Phase 3 | **No vertical work starts until:** extraction reliability is measurable (2A complete) and at least one full case has run with observable confidence metrics. Fraud vertical installs as a complete package. Insurance vertical processes a real claim end-to-end. Both run on the same engine with no engine modifications. |
| Phase 4 | Multi-user orgs with role-based access. Platform runs on AWS. Two paying clients in different verticals. New vertical takes one week to install, not one month. |
