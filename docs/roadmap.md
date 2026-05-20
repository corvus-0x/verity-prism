# Verity Prism — Product Roadmap

**Last updated:** 2026-05-20  
**Purpose:** High-level direction for all four phases. Not a task plan — that lives in `docs/superpowers/plans/`. This is the WHAT and WHY so nothing gets lost between phases.

---

## Phase 1 — Core IDP Platform + Fraud Vertical 1
**Goal:** A working document processing engine with fraud investigation tools. One investigator, one case at a time.  
**Status:** In progress — Tasks 1-8 complete, Tasks 9-11 remaining.

### What Phase 1 Delivers
- Document upload → OCR → AI extraction → structured database fields
- 11 document type schemas (PARCEL-RECORD, DEED, 990, SOS-FILING, UCC, BUILDING-PERMIT, AUDIT-REPORT, SCREENSHOT, OBITUARY, PLAT, CORRESPONDENCE)
- XML direct parse path for IRS 990 filings
- Workspace management, entities, relationships, transactions
- Fraud signal types (SR-001 through SR-026)
- Findings, investigation leads, notes
- NLP search (Task 9) — plain-English queries across extracted fields
- AI chat (Task 10) — Claude with full workspace context
- Basic React frontend (Phase 1 frontend plan)

### What Phase 1 Does NOT Include
- Public data integrations (IRS, SOS, county auditor APIs)
- Automated signal detection
- Network graph visualization
- Multi-user collaboration
- Referral package generation

---

## Phase 2 — Public Data + Guided Workflow
**Goal:** The platform pulls data, not just accepts uploads. Investigations gain structure and automation.  
**Trigger:** Start after all Phase 1 tests pass and frontend delivers working workspace UI.

### 2A — Public Data Integrations
Connect the loose ends from Phase 1 to live data sources.

**IRS 990 Import**  
- New service: `app/services/public_data.py`
- New endpoint: `POST /workspaces/{id}/import/990` — accepts EIN, fetches XML from TEOS, runs pipeline
- Wraps: `scripts/fetch_990_xml.py` (already built — see build-inventory.md)
- Scheduled option: annually check for new filings on watched EINs

**Ohio Secretary of State**  
- Entity search by name or EIN → ingest as SOS-FILING documents
- UCC financing statement search by debtor name → ingest as UCC documents
- Real-time lookup, not bulk download

**County Auditor Records**  
- Darke County: `darkecountyrealestate.org` — parcel record lookup by address or parcel number
- Mercer County: `auditor.mercercountyohio.gov` — same
- Output: PARCEL-RECORD documents in the pipeline
- Parcel numbers extracted from deeds can trigger automatic auditor lookups

**Building Permit Integration**  
- County permit data is currently ingested as Excel spreadsheets
- Phase 2: Direct API or scraper to pull permit history by address
- Output: BUILDING-PERMIT documents

**Additional Document Schemas (Phase 2)**  
- NEWS-ARTICLE — news coverage of investigation subjects
- COURT-FILING — judgments, filings
- INSURANCE-FORM — Vertical 2 preparation (see Phase 3)

### 2B — Signal Detection Engine
Automated detection of fraud signals across workspace documents.

**How it works:**  
After each document is fully extracted, the signal engine queries `document_extractions` for patterns that match signal definitions. It creates findings automatically and surfaces them in the workspace.

**Key signals to automate:**
- SR-021 REVENUE_SPIKE: Compare `total_revenue_cy` across 990s for same EIN — fire if >500% YoY increase
- SR-026 CONSTRUCTION_OVERAGE: Compare `estimated_value` (building permit) to `total_revenue_cy` (990) for same year
- SR-004 UCC_BURST: Find multiple UCC documents for same `original_fs_number` with `filing_time` within 15 minutes
- SR-025 FALSE_DISCLOSURE: 990 `gov_related_entity = false` when DEED or SOS documents show same signatory controlling multiple entities
- SR-005 ZERO_CONSIDERATION: DEED `conveyance_fee_exempt = true` + `seller_is_individual = true`
- SR-003 VALUATION_ANOMALY: DEED `sale_amount` > 2x PARCEL-RECORD `appraised_value_current`

**Output:** Auto-created Findings with evidence links to the triggering documents.

### 2C — Network Graph
Visual map of entity relationships, property chains, and transaction flows.

**Data source:** Everything already in `entities`, `relationships`, `transactions`, and `document_extractions` tables  
**Frontend:** D3.js or similar — nodes are entities, edges are relationships/transactions  
**Key queries:**
- "Show all entities connected to this nonprofit"
- "Show all properties that changed hands through this network"
- "Show the UCC lien chains for these debtors"

### 2D — Investigation Timeline
Chronological view of all events in a workspace — deed recordings, 990 filings, UCC amendments, permit dates, SOS filings — ordered by date.

**Data source:** Extracted date fields from all document types  
**Purpose:** The Catalyst problem that started this — events visible in sequence reveal patterns invisible in isolation

### 2E — Alembic Migration (Carry-forward from Phase 1)
The `no_schema` enum value and `extraction_error` column were added directly to the live DB in Task 8. Need a proper Alembic migration before Phase 2 starts so clean rebuilds work.

---

## Phase 3 — Collaboration + Referral + Insurance Vertical
**Goal:** More than one investigator. Cases move to agencies. A second vertical proves the platform generalizes.  
**Trigger:** Start after Phase 2 public data integrations are stable and at least one full case has run end-to-end.

### 3A — Multi-User Collaboration
- Workspace roles already exist in the data model (owner, analyst, viewer)
- Phase 3 wires the roles into the UI: analysts can edit, viewers are read-only
- Activity feed: who added what, when
- @mention in notes triggers notifications
- Case assignment: leads can be assigned to specific users

### 3B — Referral Package Generation
A case is useful only if it goes somewhere. This feature exports an investigation to the format each receiving agency expects.

**Referral targets:**
- Ohio Attorney General (Charitable Law Section) — narrative + evidence exhibit list
- IRS Form 13909 — tax-exempt organization complaint
- FBI IC3 — internet crime referral
- Farm Credit Administration OIG — if agricultural lending is involved

**What the package contains:**
- Executive summary (AI-generated from workspace context)
- Chronological timeline of events
- Entity relationship diagram
- Evidence exhibit list with document references
- Signal findings with supporting document citations

**Format:** PDF export + optional structured data export

### 3C — Insurance Vertical (Vertical 2)
**The pain point:** Insurance adjusters and claims teams receive paper forms (ACORD forms, medical records, property appraisals, contractor invoices) that get re-keyed into systems manually. Hours of data entry per claim.

**What the platform does:**
- Upload insurance form PDFs → extract into structured fields
- INSURANCE-FORM schema already partially designed
- Cross-reference extracted data against existing records (property records, prior claims)
- Flag discrepancies automatically

**Integration target:** Whatever system the client already uses — API push to their claims system, or structured export

**Contact:** Insurance vertical contact is documented in memory files (Vertical 2 context).

---

## Phase 4 — Scale + Deploy + Additional Verticals
**Goal:** Production-grade. More than one client. Additional verticals without rebuilding.  
**Trigger:** Phase 3 complete, at least one paying customer in each of two verticals.

### 4A — AWS Deployment
- Docker Compose → AWS ECS or EKS
- PostgreSQL → RDS
- File storage → S3
- Background jobs → SQS + Lambda or ECS tasks
- CDN for frontend assets

### 4B — Performance at Scale
- OCR is the bottleneck — consider dedicated OCR workers
- Claude API calls are per-document — batch where possible, cache extraction results
- FTS index updates are synchronous — move to async queue for large uploads
- Database indexes — review query patterns after real usage data exists

### 4C — Additional Verticals
Each vertical is a new layer on top of the IDP core — new signal types, new schemas, new referral templates.

**Candidates after insurance:**
- Legal discovery — contracts, deposition transcripts, court filings
- Real estate title work — chain of title analysis, lien searches
- Compliance audit — corporate governance documents, board minutes, policy docs
- Nonprofit oversight — expand beyond fraud vertical to general 990 analysis

**The platform's promise:** New vertical = new schemas + new signal types + new referral format. Core IDP engine doesn't change.

---

## Cross-Phase Principles

**Every phase delivers working software.**  
Don't start Phase 3 until Phase 2 is stable. Don't accumulate technical debt across phase boundaries.

**The build inventory stays current.**  
See `docs/build-inventory.md`. Every component built gets an entry. Every loose end gets a Phase destination.

**New document types follow the established pattern.**  
Examples → read documents → derive schema → seed → done. Pipeline picks it up automatically.

**The investigation case remains the reference implementation.**  
Every new feature gets validated against the fraud vertical use case before being generalized. If it doesn't make investigation better, it waits.

---

## Phase Completion Criteria

| Phase | Done when |
|---|---|
| Phase 1 | All 11 backend tasks pass. Frontend delivers working workspace with document upload, search, and AI chat. |
| Phase 2 | At least 3 public data sources integrated. Signal detection fires automatically on new documents. Network graph renders. |
| Phase 3 | Two investigators can collaborate on one case. A complete referral package can be exported. Insurance vertical processes its first real claim. |
| Phase 4 | Platform runs on AWS. Two paying customers in different verticals. Onboarding a new vertical takes one week, not one month. |
