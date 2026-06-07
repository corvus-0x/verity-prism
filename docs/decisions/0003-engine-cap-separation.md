# ADR 0003 — Engine / vertical cap separation

**Status:** Accepted  
**Date:** 2026-05-20

---

## Context

The platform serves multiple industries: fraud investigation, insurance claims, legal discovery, compliance. Each domain has its own document types, its own signal patterns, its own workflow, and its own export format.

Two structural options:

**Option A — Monolith**  
All domain logic lives in the engine. Fraud signals, insurance workflows, legal schemas — all in one codebase. Customers get everything; configuration controls what's visible.

**Option B — Engine + caps**  
The engine contains no domain knowledge. Vertical caps install on top. Each cap is a self-contained package: schema set, signal rules, workflow config, UI labels, export formats.

---

## Decision

Engine / cap separation.

**Engine** — ships to every customer, every vertical. Contains no domain logic. Processes documents, extracts fields, indexes data, answers queries. The engine knows what a document is. It does not know what fraud is.

**Vertical cap** — installs on top of the engine for a specific domain. A fraud customer installs the engine + fraud cap. An insurance customer installs the engine + insurance cap. The fraud cap never ships to an insurance customer.

```
                    VERITY PRISM ENGINE
         (document processing, extraction, search, AI)
                           │
          ┌────────────────┼────────────────┐
          ▼                ▼                ▼
     FRAUD CAP      INSURANCE CAP     [FUTURE CAP]
   (SR signals,    (claims signals,   (legal, title,
    referral fmt)   claims workflow)   compliance...)
```

The line in code: if a component knows what fraud is, it belongs in the fraud cap, not the engine.

---

## Consequences

**What gets easier:**

- Engine improvements (better OCR, faster extraction, new AI tools, additional connectors) benefit all verticals automatically without touching vertical logic.
- Adding a new vertical means writing a cap — new schema set, signal definitions, workflow config. The engine doesn't change.
- A fraud customer never sees insurance signal logic. An insurance customer never sees fraud referral formats. Separation is structural, not just configuration.
- `workspace.vertical` drives routing at runtime. The signal engine checks which cap to apply. The schema registry scopes which document types are active. The UI sidebar shows which sections are relevant.

**What gets harder:**

- Requires discipline. Domain logic can leak into engine code — the `SignalType` seed data currently in `findings.py` is a known example of this (tracked, moving to fraud cap installer in Phase 3). The boundary has to be actively maintained.
- Shared schemas (PARCEL-RECORD, for example) exist in both fraud and insurance contexts. Tagging them `general` in the schema registry handles this, but it requires deliberate thought about what belongs to a domain vs. what's genuinely domain-agnostic.

**What this rules out:**

- Shared signal logic across verticals. If fraud and insurance both need to detect "property value anomaly," each cap defines its own rule against the same underlying extracted fields. Shared rules would couple the caps — a change for insurance would affect fraud. Each cap owns its own definitions.

**Current state:**

- Engine: complete (Phase 1 + hardening)
- Fraud cap: schema set complete, signal definitions documented, framework (Phase 2B) and packaging (Phase 3A) pending
- Insurance cap: contact identified, schema set and signal definitions to be defined in Phase 3B
