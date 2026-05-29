# Verity Prism — Product Roadmap

**Last updated:** 2026-05-28  
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
**Status:** In progress — 2A complete. Next: 2C UI completeness (real-time status, export, audit log UI). 2B signal framework and 2D connectors follow.

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
The engine gains the ability to define and evaluate signals. The signals themselves are defined by verticals — this is the framework that runs them. **Requires 2A complete** — signals fire on extracted field values; those values need to be reliable before signals mean anything.

**How it works:**
- A `signal_rules` table stores pattern definitions (field + operator + threshold + signal code)
- After extraction completes, the signal engine evaluates all active rules for the workspace's vertical
- Matching rules auto-create Findings with evidence links
- New signals = new rows in `signal_rules`, no code change

**What the framework provides:**
- Rule evaluation engine (queries `document_extractions`, compares values)
- Cross-document rules (compare fields across multiple documents for same entity)
- Time-series rules (compare field values across filing years)
- Threshold rules (field value > X, or ratio between two fields > Y)

**What the framework does NOT contain:** Any specific rule definitions. Those live in the vertical cap.

### 2C — Engine UI Completeness
These are engine-level UI capabilities that any vertical needs. Not vertical-specific — they ship with the engine and are available in every workspace.

**Real-time extraction status** 🔲:  
Currently the pipeline runs in the background with no feedback until the user polls. Server-sent events (SSE) on `GET /workspaces/{id}/documents/{doc_id}/status/stream` push `pending → processing → complete/failed` to the frontend in real time. The document list updates live without refresh. Pairs with the document viewer — the viewer opens when extraction completes.

**Data export** 🔲:  
`GET /workspaces/{id}/documents/{doc_id}/extractions.csv` and `/extractions.json` — download all extracted fields for a document as structured data. Also workspace-level export: all extractions across all documents in a workspace as a flat CSV. This is asked for in every evaluation. Generic export is engine-level; vertical-specific export formats (AG referral package, claims API push) remain in the vertical cap.

**Audit log UI** 🔲:  
The audit log is immutable at the DB level (PostgreSQL trigger). Surfacing it in the UI makes it a selling point. A simple chronological list per workspace: who did what, when, on which document. Read-only. Compliance language: "every action on every document is logged and tamper-proof."

### 2D — Data Connectors
Public data sources feed directly into the pipeline. Any vertical can use any connector. **Can run parallel to 2B** — connectors are input to the pipeline, not dependent on the intelligence layer. Can also run parallel to 2C.

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

**Existing asset:** `scripts/fetch_990_xml.py` is the core IRS TEOS logic. Phase 2C wraps it in the connector service.  
**Scheduled option:** Background job checks for new filings on watched EINs annually.  
**Cross-vertical use:** Fraud uses IRS TEOS for 990s. Insurance uses county auditor for property data. Same connector serves both.

---

## Phase 3 — Vertical Packaging
**What it is:** The engine gets its first two caps. Each vertical is a complete, installable package.  
**Trigger:** Phase 2A (extraction eval + observability) complete. Engine extraction is measured and reliable. At least one full end-to-end case has run against real documents with observable confidence metrics.

### 3A — Fraud Vertical v1.0
**Installs:** Fraud schema set + SR signal definitions + investigation workflow + referral export

**Schema set (already built, just needs vertical packaging):**
PARCEL-RECORD, DEED, 990, SOS-FILING, UCC, BUILDING-PERMIT, AUDIT-REPORT, SCREENSHOT, OBITUARY, PLAT, CORRESPONDENCE

**Signal definitions (SR-001 through SR-026 — using Phase 2B framework):**
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
Don't start Phase 3 until Phase 2 connectors and signal framework are stable. Don't let verticals leak into engine phases.

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
| Phase 2 | ✅ Document viewer live (field-level linking deferred to follow-on). Extraction eval loop running with retry/escalate. Observability logging all Claude calls with confidence distribution. Real-time extraction status via SSE. Export working for documents and workspaces. Audit log UI live. Signal framework evaluates rules without code changes. Three connectors integrated. |
| Phase 3 | **No vertical work starts until:** extraction reliability is measurable (2A complete) and at least one full case has run with observable confidence metrics. Fraud vertical installs as a complete package. Insurance vertical processes a real claim end-to-end. Both run on the same engine with no engine modifications. |
| Phase 4 | Multi-user orgs with role-based access. Platform runs on AWS. Two paying clients in different verticals. New vertical takes one week to install, not one month. |
