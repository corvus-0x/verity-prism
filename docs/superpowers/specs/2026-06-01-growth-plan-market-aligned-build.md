# Verity Prism — Growth Plan: Market-Aligned Build Sequence + Vertical Cap Architecture

**Date:** 2026-06-01  
**Status:** Approved for implementation planning  
**Scope:** Phase A (foundation), Phase B (market additions), Phase C (vertical cap)

---

## Context

### What exists

Verity Prism is a complete IDP engine. Phase 1 through Phase 2F are done: document ingestion, field extraction, schema registry, NLP search, AI chat with tool-use, observability dashboards, data connectors, extraction review, audit log, and commercial readiness (prompt caching, model routing, usage metering). 222 passing tests. The engine has never been driven end-to-end with a full real case.

### What Catalyst contributes

Catalyst (corvus-0x/catalyst on GitHub) is the predecessor investigation platform built on Django. It contains working domain knowledge that Phase 3 needs:

| Catalyst file | Size | What it becomes in Prism |
|---|---|---|
| `signal_rules.py` | 88KB | `app/caps/fraud/signal_rules.py` |
| `referral_export.py` | 25KB | `app/caps/fraud/export.py` |
| `entity_extraction.py` | 54KB | Service layer input to fraud cap |
| `entity_normalization.py` + `entity_resolution.py` | 40KB | Fraud cap entity pipeline |
| `ohio_sos_connector.py` | 30KB | `app/services/connectors/ohio_sos.py` |
| `county_auditor_connector.py` | 68KB | `app/services/connectors/county_auditor.py` |
| `county_recorder_connector.py` | 84KB | `app/services/connectors/county_recorder.py` |
| `.github/workflows/ci.yml` | — | Adapt for Prism's test suite |
| `railway.json` | — | Adapt for Prism deployment |

Catalyst's architectural failure was `views.py` at 238KB — all business logic collapsed into a single Django views file. Prism's thin routers → services → models pattern exists specifically to prevent this. Porting Catalyst domain logic means extracting it from views and placing it in the correct layer.

### Why this plan exists

Nine job descriptions were analyzed to identify skill gaps between what Prism demonstrates and what the current AI engineering job market asks for. The plan closes those gaps by adding real capabilities to the platform — not tutorial projects — so every technology listed on the resume has a working use case behind it.

---

## Strategic Goal

Build Prism correctly and completely. Every addition in this plan serves both the product and the portfolio. Nothing is added for resume keywords alone.

---

## Build Sequence

```
Phase A — Foundation (unlocks everything else)
  ├── GitHub Actions CI/CD
  └── End-to-end case validation

Phase B — Market-Relevant Additions (closes skill gaps)
  ├── Output format normalization
  ├── LangSmith integration
  └── PGVector hybrid search

Phase C — Vertical Cap Architecture (portfolio centerpiece)
  ├── Cap installer pattern
  ├── Signal engine framework
  └── Fraud cap v1 (ported from Catalyst)
```

Each phase is a prerequisite for the next. The demo capability Phase A produces is needed for Swivl, Iovance, and the public safety role interviews. The market additions in Phase B are needed before Phase C to ensure signal detection has clean data. Phase C is the architectural work that demonstrates engineering judgment beyond tool familiarity.

---

## Phase A — Foundation

### A1: GitHub Actions CI/CD

**What:** Run Prism's 222-test suite on every PR automatically.

**Source:** Catalyst already has `.github/workflows/ci.yml`. Adapt it for Prism's pytest + Docker Compose test setup rather than building from scratch.

**Implementation:**
- New file: `.github/workflows/ci.yml`
- Spins up PostgreSQL service container
- Runs `docker-compose run --rm backend pytest tests/ -v`
- Runs `ruff check` and `npx tsc --noEmit` for frontend type check
- Triggers on push to any branch and on pull_request to main

**Why this matters for interviews:** CI/CD appears in 4+ JDs. More importantly, a green badge on the repo is visible to any hiring manager who looks at GitHub before a phone screen.

### A2: End-to-End Case Validation

**What:** Drive the real investigation documents through the full platform pipeline and observe actual system behavior.

**Process:**
1. Upload 15-20 documents from the real investigation: deeds, 990s, SOS filings, building permits, parcel records, correspondence
2. Observe automation rate — what percentage reach `complete` without human review
3. Review confidence score distribution — are scores meaningful or clustering artificially high
4. Run 10+ NLP searches against extracted data — verify results are correct
5. Use AI chat to surface connections across documents — verify tool calls return useful data
6. Document findings: which document types extract cleanly, which fail or fall to review queue, what the actual automation rate is

**Deliverable:** A written findings note (private/) documenting the baseline automation rate, confidence distribution, and any extraction failures. This becomes the demo script for interviews and the baseline for measuring Phase B improvements.

**Why this is a prerequisite:** You cannot confidently demo a platform you have never driven end-to-end. The public safety role, Swivl, and Iovance all require live demos. Phase B improvements are only measurable if Phase A establishes a baseline.

---

## Phase B — Market-Relevant Additions

### B1: Output Format Normalization

**What:** A normalization layer applied to raw extracted values before they are stored in `document_extractions`. Configured per field in `schema_fields` JSON.

**Why this is a prerequisite for signal detection:** Signal rules compare field values. SR-003 (VALUATION_ANOMALY) compares `sale_amount` against `appraised_value_current`. If `sale_amount` is stored as `$1,250,000.00` in one document and `1250000` in another, the comparison silently fails. Normalization ensures signal detection compares numbers against numbers.

**Normalization types (confirmed from Phase 2E spec):**
- `remove_chars` — strip symbols (remove `$`, `#`, `,`)
- `date_format` — convert to standard format (`01.05.2026` → `05/01/2026`)
- `case` — upper / lower / sentence
- `format_number` — normalize currency and decimals to plain numeric string
- `find_replace` — swap string variants at runtime
- `truncate` — trim N chars from left or right

**Where it lives:** New function `normalize_value(raw, rules)` in `app/services/extraction_engine.py`, called by `save_extractions()` before writing to DB. No new table — normalization config lives in `schema_fields` JSON.

### B2: LangSmith Integration

**What:** Wire LangSmith tracing into Prism's extraction pipeline and AI chat agent alongside the existing `claude_call_logs` table.

**Why LangSmith specifically:** Named explicitly in the Nephew JD. Widely used across AI engineering teams. The existing `claude_call_logs` infrastructure demonstrates the concept, but hiring managers at AI-native companies recognize LangSmith by name.

**Integration points:**
- `app/services/claude_client.py` — wrap the `get_client()` singleton with LangSmith's `wrap_anthropic()` decorator
- `app/services/ai_engine.py` — add `langsmith_tracer` to the chat loop so each tool-use round is a traced span
- `app/services/extraction_engine.py` — each `_extract_batch` call becomes a traced span with schema name, field count, and document id as metadata

**Architecture decision:** LangSmith traces run alongside `claude_call_logs`, not instead of it. `claude_call_logs` is the production billing/metering data source. LangSmith is the debugging and evaluation interface. Both serve different purposes and both should exist.

**New environment variable:** `LANGSMITH_API_KEY` added to `backend/.env.example`.

### B3: PGVector Hybrid Search

**What:** Add semantic similarity search alongside the existing FTS + field-filter search, creating a hybrid retrieval system.

**Why hybrid, not replacement:** FTS is better for structured queries (`sale_amount > 1000000`, `grantee_name = "Oak Ridge LLC"`). PGVector is better for semantic similarity (`find documents similar to this deed`, `find documents about nonprofit governance`). Removing FTS would make signal detection harder. Keeping both and routing by query type is the production pattern.

**Implementation:**
- Add `pgvector` extension to PostgreSQL via migration
- New column: `document_extractions.embedding` (vector, 1536 dimensions — matches `text-embedding-3-small`)
- New service: `app/services/embedding_service.py` — `generate_embedding(text)` calls OpenAI embeddings API (or Anthropic when available), returns vector. Triggered after `save_extractions()` for each document.
- `app/services/search_service.py` — add `semantic_search(query, workspace_id, db)` path alongside existing `run_search()`. New `translate_query()` logic detects whether query is a structured filter (`field_name operator value`) or a natural language similarity query and routes accordingly.
- New endpoint: `POST /workspaces/{id}/search/` accepts `mode: "keyword" | "semantic" | "hybrid"`. Default: `"hybrid"` — runs both, merges results by relevance score.

**Migration:** `app/alembic/versions/` — new migration adds pgvector extension and embedding column.

**Interview story:** "I added PGVector alongside FTS because the use cases are different. Structured field queries need keyword precision — signal detection depends on exact value comparison. Semantic similarity needs embeddings — 'find documents like this one' is a different problem. Running both lets the system route to the right mechanism for the question being asked."

---

## Phase C — Vertical Cap Architecture

### C1: Cap Installer Pattern

**What:** The `app/caps/` directory establishes the contract that every vertical follows. One installer installs one vertical. The engine doesn't change.

**Structure:**
```
app/caps/
    __init__.py           — get_cap(vertical), list_caps()
    base.py               — CapBase contract
    fraud/
        __init__.py
        installer.py      — FraudCap(CapBase) — seeds schemas, signal types, workflow
        signal_rules.py   — SR-001 through SR-026 (ported from Catalyst)
        export.py         — AG/IRS/FBI/OIG referral formats (ported from Catalyst)
        agent_tools.py    — fraud-specific agent tools (network graph, timeline)
    insurance/
        __init__.py
        installer.py      — InsuranceCap(CapBase) — placeholder, Phase 3B
```

**CapBase contract (`app/caps/base.py`):**
```python
class CapBase:
    vertical: str           # matches workspace.vertical
    display_name: str
    schema_tags: list[str]  # which schema vertical tags this cap activates
    signal_types: list[dict]
    agent_tools: list       # additional tools beyond the 7 core tools
    
    def install(self, db) -> None:
        # seeds signal types, validates schemas exist, registers tools
        raise NotImplementedError
    
    def uninstall(self, db) -> None:
        # removes cap-specific seed data (signal types, cap-tagged schemas)
        raise NotImplementedError
```

**Installation trigger:** `POST /admin/caps/{vertical}/install` — admin-only endpoint. In SaaS: called during account provisioning. In self-hosted: called once after deploy. The engine runs without any cap installed (General workspaces). Installing a cap adds domain content; no code changes required.

**Frontend impact:** `WorkspaceSidebar.jsx` already reads `workspace.vertical` and uses `VERTICAL_SECTIONS` map — adding a new vertical's nav is one entry in that map. No other frontend changes needed for the installer pattern.

### C2: Signal Engine Framework

**What:** `app/services/signal_engine.py` evaluates signal rules from the `signal_rules` table against `document_extractions` for a workspace.

**Signal rule structure (`signal_rules` table):**
```
signal_code       — SR-003
signal_name       — VALUATION_ANOMALY  
vertical          — fraud
rule_type         — comparison | threshold | pattern | cross_document
field_a           — sale_amount
operator          — gt
field_b           — appraised_value_current
multiplier        — 2.0
severity          — high | medium | low
description       — human-readable explanation
```

**Engine behavior:**
- Triggered after extraction completes and normalization runs
- Loads rules for the workspace's vertical from `signal_rules` table
- Evaluates each rule against the document's extracted fields
- Creates `Finding` records for triggered rules with source document, field values, and rule code
- Writes audit log entry for each finding created

**Source:** Rule definitions come from Catalyst's `signal_rules.py` (88KB). The logic is already written and tested against real documents. The work is extracting rule definitions from Catalyst's class-based approach into the `signal_rules` table rows and writing the engine evaluator against that structure.

### C3: Fraud Cap v1

**What:** The first complete vertical cap. Installs on top of the engine for fraud investigation workspaces.

**Components:**

*Schemas* — Already built in the schema registry. PARCEL-RECORD, DEED, 990, SOS-FILING, UCC, BUILDING-PERMIT, AUDIT-REPORT, SCREENSHOT, OBITUARY, PLAT, CORRESPONDENCE. OBITUARY is already tagged `vertical="fraud"`. The remaining schemas are `general` — available in all workspaces.

*Signal types* — SR-001 through SR-026 seeded by `FraudCap.install()`. Currently misplaced in `findings.py` router — moved to `app/caps/fraud/installer.py`. Full rule definitions ported from Catalyst's `signal_rules.py`.

*Connectors* — Three connectors promoted from 🔲 Planned to ✅ Connected by porting from Catalyst:
- `app/services/connectors/ohio_sos.py` — from Catalyst's `ohio_sos_connector.py`
- `app/services/connectors/county_auditor.py` — from Catalyst's `county_auditor_connector.py`
- `app/services/connectors/county_recorder.py` — from Catalyst's `county_recorder_connector.py`

Each port: extract connector logic from Catalyst's file, implement `ConnectorBase` contract (`search()` → `list_items()` → `fetch()`), register in `connector_registry.py` with `vertical="fraud"`.

*Network graph* — Visual entity-relationship map. The engine provides `entities` and `relationships` tables. The fraud cap provides the React component and decides which connections to surface. D3.js force-directed graph already exists in Catalyst's frontend — adapt for Prism's workspace context.

*Investigation timeline* — Chronological view of fraud-relevant events. The fraud cap selects which extracted date fields matter (deed recording dates, 990 filing dates, UCC amendment timestamps, permit issuance dates). The engine provides the extracted values.

*Referral export* — AG/IRS/FBI/OIG complaint package formats. Ported from Catalyst's `referral_export.py` into `app/caps/fraud/export.py` under Prism's service layer pattern.

*Fraud-specific agent tools* — Extend the 7 core tools with:
- `get_network_graph(workspace_id)` — returns entity connections for Claude to reason about
- `get_timeline(workspace_id)` — returns chronological fraud-relevant events

Registered in `app/caps/fraud/agent_tools.py`, added to `VERTICAL_TOOLS["fraud"]` in `agent_registry.py`.

---

## Job Market Alignment

| Addition | Closes gap in | JDs affected |
|---|---|---|
| GitHub Actions CI/CD | CI/CD experience visible on repo | Right-Hand, Stability, Junior SE |
| LangSmith | Named explicitly | Nephew; implied in Kalmus, Remora |
| PGVector hybrid search | RAG + vector search gap | Kalmus, Remora, Stability |
| Output format normalization | Signal detection correctness | Internal — enables Phase C |
| Cap installer pattern | Composable behavior / "skills" | Nephew, Swivl |
| Signal engine | Agent evaluation, domain logic | Nephew, Iovance, public safety |
| Fraud cap v1 | Full vertical demo | Iovance, public safety, Crosstie |
| End-to-end validation | Live demo capability | Swivl, Iovance, public safety |

---

## Catalyst Migration Rules

When porting Catalyst code into Prism:

1. **Extract from views, not copy.** Business logic lives in `views.py`. Pull it out and place it in `app/services/` or `app/caps/fraud/`. Never copy a Django view into a FastAPI router.

2. **Implement the contract.** Connectors must implement `ConnectorBase`. Cap logic must implement `CapBase`. The contract is what makes the pattern pluggable.

3. **Write the test first.** Every ported component gets a failing test before the port begins. Catalyst's 500+ tests are a reference for what behavior to verify, not code to copy.

4. **Strip domain content from the engine.** If ported code knows what fraud is, it belongs in `app/caps/fraud/`, not `app/services/`.

5. **Normalize field names.** Catalyst's field naming conventions differ from Prism's schema field names. Map explicitly; do not assume.

---

## Success Criteria

| Phase | Done when |
|---|---|
| Phase A | Green CI badge on Prism repo. Real case loaded, automation rate documented, demo script written. |
| Phase B | Normalization running on all `claude` parse_strategy extractions. LangSmith traces visible in project dashboard. Semantic search returning results alongside keyword search. |
| Phase C | `FraudCap.install()` seeds all SR signal types and registers connectors. Signal engine fires SR-003 against a deed with valuation anomaly. Network graph renders entity connections. Referral export generates AG-format package. |
