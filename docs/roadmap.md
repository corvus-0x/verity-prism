# Verity Prism — Product Roadmap

**Last updated:** 2026-05-20  
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
│  │  index       │  │  field parse │  │  network graph │ │
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
  │  Investigation │  │  Claims signals │  │  Real estate     │
  │  workflow      │  │  Claim workflow │  │  title           │
  │  AG/IRS/FBI    │  │  Claims system  │  │  ...             │
  │  referral      │  │  export         │  │                  │
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
**Status:** In progress — Tasks 1-8 complete, Tasks 9-11 remaining.

### Engine capabilities delivered in Phase 1
- Document ingestion: SHA-256 evidence lock → OCR → type detection → field extraction → FTS index
- Schema registry: 11 document type schemas, plug-and-play, no code change to add new types
- XML direct parse path: structured files (990 XML) bypass OCR, extracted at full confidence
- Background processing: upload returns immediately, pipeline runs async
- Fail-fast error handling: `failed` / `no_schema` statuses, auto-lead creation for unknown types
- Workspace management, entities, relationships, transactions, notes
- Audit log: immutable, PostgreSQL trigger-enforced
- NLP search — Task 9: plain-English queries across all extracted fields
- AI chat — Task 10: Claude with full workspace context
- React frontend — Phase 1 frontend plan

### What Phase 1 does NOT include
- Any vertical-specific logic
- Public data connectors
- Signal detection
- Multi-user collaboration

---

## Phase 2 — IDP Engine Capabilities
**What it is:** The engine gets smarter and more connected. No vertical logic — these capabilities serve all verticals equally.  
**Trigger:** All Phase 1 tasks complete, frontend working.

### 2A — Data Connectors
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

**Existing asset:** `scripts/fetch_990_xml.py` is the core IRS TEOS logic. Phase 2A wraps it in the connector service.  
**Scheduled option:** Background job checks for new filings on watched EINs annually.  
**Cross-vertical use:** Fraud uses IRS TEOS for 990s. A tax compliance vertical uses the same connector for the same reason. Insurance uses county auditor for property data.

### 2B — Signal Detection Framework
The engine gains the ability to define and evaluate signals. The signals themselves are defined by verticals — this is the framework that runs them.

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

### 2C — Relationship & Network Graph
Visual map of entities, properties, transactions, and document links.

**Data source:** Everything already in `entities`, `relationships`, `transactions`, `document_extractions`  
**Value:** Patterns invisible in tables become obvious as a graph  
**Cross-vertical:** Fraud uses it for entity networks. Insurance uses it for claim relationships.

### 2D — Investigation Timeline
Chronological view of all extracted dates across all documents in a workspace.

**Data source:** Every date field extracted from every document type  
**Value:** Events in sequence reveal what isolated documents don't

### 2E — Alembic Migration (carry-forward)
`no_schema` enum value and `extraction_error` column were added directly to the DB in Task 8. Need a proper Alembic migration before Phase 2 so clean rebuilds work.

---

## Phase 3 — Vertical Packaging
**What it is:** The engine gets its first two caps. Each vertical is a complete, installable package.  
**Trigger:** Phase 2 engine capabilities stable. At least one full end-to-end case has run.

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

**Investigation workflow:**
Upload → extract → signals fire → findings created → investigator reviews → referral package

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

### 4A — AWS Deployment
Docker Compose → AWS ECS/EKS. PostgreSQL → RDS. Files → S3. Background jobs → SQS. CDN for frontend.

### 4B — Additional Vertical Caps
Each new vertical is a schema set + signal definitions + workflow config + export format. The engine doesn't change.

**Candidates:**
- Legal discovery — contracts, depositions, court filings, privilege review
- Real estate title — chain of title analysis, lien searches, closing packages
- Compliance audit — board minutes, policy docs, governance review
- Nonprofit oversight — general 990 analysis beyond the fraud vertical

**Time to add a new vertical:** With the Phase 2 framework in place, a new vertical should take weeks, not months. Schema derivation (one session per document type, as established in Phase 1) + signal definitions + workflow config.

### 4C — Vertical Marketplace
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
| Phase 1 | All 11 backend tasks pass. Frontend delivers working workspace with upload, search, and AI chat. Documents flow through the full pipeline end-to-end. |
| Phase 2 | Three connectors integrated and tested. Signal framework evaluates rules without code changes. Network graph renders entity relationships. Timeline view shows extracted dates in sequence. |
| Phase 3 | Fraud vertical installs as a complete package. Insurance vertical processes a real claim end-to-end. Both verticals run on the same engine with no engine modifications. |
| Phase 4 | Platform runs on AWS. Two paying clients in different verticals. New vertical takes one week to install, not one month. |
