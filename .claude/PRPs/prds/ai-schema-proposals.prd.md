# AI Schema Proposals — Self-Learning Document Universe

## Problem Statement

When a document arrives whose type has no schema, Verity Prism marks it `no_schema`, files an investigation lead, and stops — a human must hand-author a schema in seed code before a single field can be extracted. And when a document *has* a schema but contains important data the schema doesn't define (e.g. a deed with a notary commission expiration the DEED schema never modeled), that data is silently never captured. The cost: the engine cannot grow its own coverage. Every new document type and every missed field is a developer task, not an operator action.

## Evidence

- `document_pipeline.py:105` `_no_schema()` — confirmed: unknown types dead-end with a lead reading *"Go to document_schemas and add a schema for this type."* That instruction is a code-edit-and-redeploy, not a product action.
- Schema creation is **seed-only today**: `schemas.py` router exposes `list` + `get` and nothing else; all schemas are authored in `seeds/document_schemas.py`.
- The gap-detection capability does not exist: `field_validator` and `extraction_evaluator` only grade fields the schema *already defines*. Neither scans OCR text for data *outside* scope.
- Operator-stated demand (this PRD's originating request): *"if a document doesn't have a schema, the AI can build one… or if a document with a built schema has something outside scope, automatically add it."*

## Proposed Solution

Add an **AI-proposes / human-approves / versioned-apply** loop on top of the existing schema-driven pipeline. The AI never mutates an active schema directly. Instead it writes a **proposal** (new schema, or a set of field additions) that an operator reviews, edits, and approves. Approval inserts a schema row — and because `detect_document_type()` and `get_schema_for_type()` both read `document_schemas` at call time, the new/updated schema becomes live with **zero redeploy**. This rides the platform's existing "schema-driven, no-redeploy" decision (ADR 0002) rather than introducing a parallel mechanism.

## Key Hypothesis

We believe **an AI schema-proposal loop with operator approval** will **let operators grow the engine's document coverage themselves — turning new types and missed fields from developer tickets into in-app actions** for **fraud/insurance investigators and engine operators**.
We'll know we're right when **an operator takes a `no_schema` document to a live, extracting schema entirely in the UI, with no code change or redeploy, and the document reprocesses to `complete`.**

## What We're NOT Building

- **Auto-apply / silent schema mutation** — explicitly rejected. AI proposes; a human approves. This is the guardrail against schema drift, duplicate field names, and unstable exports.
- **In-place field append without a version bump** — rejected in favor of full supersession (decision below).
- **Workspace-scoped schemas** — schemas stay global/shared engine contract (decision below). Not changing `document_schemas` to carry `workspace_id`.
- **Auto-reprocessing of historical documents on apply** — reprocess stays an explicit, opt-in action per document. Old docs keep their pinned `schema_id` until someone reprocesses them.
- **Re-detecting type on already-classified docs** — Feature 2 scans the doc against its *current* schema; it does not re-run type detection.

## Success Metrics

| Metric | Target | How Measured |
|--------|--------|--------------|
| `no_schema` → `complete` fully in-app (no redeploy) | Works end-to-end for ≥1 real unknown doc type | Manual acceptance: upload unknown doc → generate draft → approve → reprocess → status `complete` |
| Proposed schema usable without heavy edits | ≥70% of AI-proposed fields kept by the operator (not deleted) on approval | Compare `proposed_fields` vs final `schema_fields` at apply time |
| Gap-scan precision (Phase 2) | ≥60% of proposed additions accepted by operator | Accepted fields ÷ proposed fields per `schema_extension` proposal |
| No silent schema ambiguity introduced | 0 cases of two `is_active=True` schemas for the same `(document_type, vertical)` | DB invariant check / test |

## Open Questions

- [ ] **Governance (the big one) — partially resolved:** apply is now **owner-only** (analyst can only draft), which is the right MVP trust boundary. The remaining question is the **org tier**: an owner in Workspace A still inserts a **global** schema visible to all workspaces. Before there are multiple teams/orgs, apply needs an org-admin gate (or org-scoped schema visibility). Tracked as the pre-GA governance follow-up — not an MVP blocker.
- [ ] Should `propose_schema_for_document` suggest a `vertical` (general vs a specific cap), or always default to `general` and let the operator pick?
- [ ] For the gap scan: do we cap the number of proposed additions per scan to keep review tractable on large schemas (e.g. the 370-field parcel record)?
- [ ] Does an applied supersession need to notify/flag documents still pinned to the old version ("12 docs are on v1; reprocess?")?

---

## Users & Context

**Primary User**
- **Who**: Engine operator / investigator (owner or analyst role) processing documents in a workspace.
- **Current behavior**: Hits a `no_schema` lead, has no in-app path forward, escalates to a developer.
- **Trigger**: An unknown document type lands, OR they notice extracted output is missing data that's plainly in the source.
- **Success state**: They resolve it themselves — draft, edit, approve, reprocess — and the field/document is now captured.

**Job to Be Done**
When **a document arrives that the engine can't fully capture (no schema, or missing fields)**, I want to **turn the document's own content into an approved schema or field set**, so I can **extract that data now without waiting on engineering.**

**Non-Users**
- End-clients consuming exports — they never see proposals; they see the resulting structured data.
- Developers maintaining seed schemas — seeds remain valid; this is additive, not a replacement.

---

## Solution Detail

### Decisions locked (this session)

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Extension versioning | **Full supersession** — apply sets v1 `is_active=False`, inserts v2 `is_active=True, version=v1.version+1` in one transaction | Clean lineage; old docs stay pinned to v1's `schema_id` until reprocessed; avoids the `.first()` ambiguity in `get_schema_for_type`. |
| Approval authority | **Apply: workspace owner only. Draft/edit: analyst.** | Apply mutates *global engine contract* — that trust boundary belongs to owner. Analysts can draft and edit but not commit. (Org-admin tier comes later, with the governance work.) |
| Schema scope | **Per-workspace proposals → global applied schemas** | Matches today's global schema model; surfaces the governance open-question rather than re-architecting tenancy. |
| MVP boundary | **Feature 1 first, Feature 2 second** | Feature 2 reuses Feature 1's table, services, and review UI; gap-scan prompt is the noisier/riskier half. |
| Proposal status lifecycle | **`draft \| rejected \| applied \| failed`** (approval *is* the apply action) | Avoids overlapping `approved`/`applied` states. Review tracking lives in `reviewed_by`/`reviewed_at`, not a separate status. |
| Supersession enforcement | **Database partial unique index** `UNIQUE(document_type, vertical) WHERE is_active=true` | Protects the invariant against future code paths, not just today's. |

### Core Capabilities (MoSCoW)

| Priority | Capability | Rationale |
|----------|------------|-----------|
| Must | `schema_change_proposals` table + lifecycle (`draft → rejected | applied | failed`) | Backbone for both features. |
| Must | `propose_schema_for_document(document_id)` — AI drafts a full schema from `ocr_text` + metadata | Feature 1 core. |
| Must | `apply_schema_proposal(proposal_id)` — insert schema (with atomic supersession for extensions) | Turns approval into live engine contract. |
| Must | `reprocess_document(document_id, schema_id)` service (promote from the existing seed) | Re-runs pipeline so the doc actually extracts. |
| Must | Create/apply/reject proposal API endpoints on the `schemas` router; **apply gated to owner role** | No write surface exists today; apply mutates global contract. |
| Must | **Server-side proposal validation on apply** (names unique/snake_case, valid types, thresholds in range, descriptions present, normalized + collision-checked `document_type`) | Human review is not sufficient; apply must validate regardless of editor. |
| Must | **DB partial unique index** `UNIQUE(document_type, vertical) WHERE is_active=true` + atomic supersession + `order_by(version.desc())` | Closes the `get_schema_for_type().first()` landmine at the durable layer. |
| Must | **Forced-schema reprocess** path (set schema_id + doc_type, skip re-detection) | Plain reprocess re-runs detection and could re-classify the doc as `OTHER`. |
| Must | **OCR precondition** on proposal generation (require non-empty `ocr_text`, error otherwise) | Prevents the AI inventing schemas from filenames. |
| Must | **Proposal provenance** (model id, prompt version, proposer inputs) on the proposal row | Schema changes are engine-contract changes; they need an explainable trail. |
| Should | Proposal review UI: draft schema editor + accept/reject | Operator-facing surface for the loop. |
| Should | `propose_schema_extensions(document_id, schema_id)` — gap scan over OCR + extracted fields | Feature 2 core. |
| Could | Bulk "reprocess all docs pinned to superseded version" action | Convenience after a supersession. |
| Won't | Auto-apply without human approval | Explicit guardrail. |
| Won't | Workspace-scoped schemas | Out of scope this cycle. |

### MVP Scope

Feature 1, end to end: upload unknown doc → `no_schema` + lead (already exists) → analyst clicks **Generate Schema Draft** (requires OCR text) → AI proposes type/display_name/vertical/parse_strategy/fields/thresholds with provenance → analyst edits → **owner applies**, which runs `validate_proposal` then inserts the schema row → **forced-schema reprocess** of the doc → status `complete`. This alone validates the hypothesis. The four hard requirements (validation, forced-schema reprocess, owner-only apply, DB-level active-schema uniqueness) are in-scope for MVP, not deferred.

### User Flow (critical path)

```
no_schema doc ──▶ "Generate Schema Draft"
     │                     │
     │           propose_schema_for_document()  (AI reads ocr_text + filename/source)
     │                     ▼
     │           proposal (status=draft, created_by_ai)
     │                     ▼
     │           analyst edits fields ──▶ owner applies
     │                     ▼
     │           validate_proposal() ──▶ apply_schema_proposal() ──▶ DocumentSchema row (live, no redeploy)
     │                     ▼
     └──────────▶ reprocess_document(doc, new_schema_id)  [forced schema] ──▶ status=complete
```

---

## Technical Approach

**Feasibility**: **HIGH** — the hard rails already exist (call-time schema loading, retained OCR text, a working reprocess routine, a human-in-loop review precedent). The net-new work is one table, ~4 service methods, two AI prompts, write endpoints, and a UI surface.

**Architecture Notes**
- **New table `schema_change_proposals`**: `id, workspace_id, document_id, base_schema_id (nullable), proposal_type ('new_schema'|'schema_extension'), status ('draft'|'rejected'|'applied'|'failed'), proposed_schema (JSONB), proposed_fields (JSONB), rationale (text), created_by_ai (bool), reviewed_by (FK users, nullable), reviewed_at (nullable), apply_error (text, nullable), created_at`, **plus provenance** (see below). Soft-delete columns (`is_deleted`, `deleted_at`) per the project-wide convention (and the `check_soft_delete.py` hook will flag any query that omits them).
- **Status lifecycle**: `draft → (rejected | applied | failed)`. Approval *is* the apply action — there is no separate `approved` state. A failed apply lands `failed` with `apply_error` captured; `reviewed_by`/`reviewed_at` record who acted and when, independent of outcome.
- **Provenance is required, not optional** (schema changes are engine-contract changes): store on each proposal the model id, the prompt template version, and the proposer inputs (`document_id`, `base_schema_id`, OCR char count / hash of the OCR slice sent). Log the Claude call via `claude_call_logs` too (call_types `schema_proposal`, `schema_gap_scan`) for cost parity — but the *why-this-schema* explanation lives on the proposal row so it survives independent of the call log.
- **Server-side validation on apply is a first-class gate** (not just human review). `apply_schema_proposal` must reject a proposal that fails any of: field names unique within the schema; field names `snake_case`; `field_type` ∈ the known type set; no reserved/confusing names; thresholds in `[0.0, 1.0]`; every field has a non-empty `description`; `document_type` normalized (upper-kebab, matching seed convention) and collision-checked; and — for `new_schema` — no existing active `(document_type, vertical)`. Validation lives in the service and is covered by tests; it runs regardless of who edited the draft.
- **Reuse, don't rebuild reprocess — but force the schema**: lift `seeds/reprocess_documents.py` into a `reprocess_document(document_id, schema_id, db)` service method, **with a forced-schema path**. The existing seed nulls `detected_doc_type` and re-runs full type detection (`reprocess_documents.py:50-51`) — which could re-classify a freshly-schema'd doc as `OTHER` and dead-end again. The forced path must instead: set `doc.schema_id` and `doc.detected_doc_type` to the approved schema's type, clear old extractions, then extract **against that schema** (skip detection + match). The seed becomes a thin caller of the non-forced path.
- **OCR precondition for proposal generation**: `propose_schema_for_document` must require non-empty `document.ocr_text` and return a clear error if OCR failed or is empty. Without it the AI would invent a schema from the filename alone. (Today `no_schema` docs *do* retain OCR via `_update_search_index`, so the happy path holds — but the guard is mandatory.)
- **Supersession is DB-enforced**: add the partial unique index `UNIQUE(document_type, vertical) WHERE is_active=true` in the migration. `apply_schema_proposal` for an extension deactivates the base schema and inserts the successor in one transaction; harden `get_schema_for_type` with `order_by(version.desc())` as defense-in-depth.
- **Thin-router discipline**: all DB logic lives in a `*_service.py` (likely extend `schema_service.py` or add `schema_proposal_service.py`); the `schemas.py` router stays validate→call→return. The `check_thin_routers.py` hook enforces this.
- **Audit every create/apply/reject action** via `audit.log()` — schema changes are engine-contract changes and must leave a trail.

**Technical Risks**

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Two active schemas per type/vertical → silent wrong-schema extraction | M | **DB partial unique index** (not just a test) + atomic supersession + `order_by(version.desc())`. |
| AI proposes noisy/duplicate field names | M | `validate_proposal` on apply (unique, snake_case, valid type, description present) — independent of human edit. |
| AI invents a schema from filename when OCR is empty | M | OCR precondition: `propose_schema_for_document` requires non-empty `ocr_text`, errors otherwise. |
| Forced reprocess silently re-detects as `OTHER` and dead-ends | M | Forced-schema reprocess path skips detection; pins schema_id + doc_type. |
| Global apply changes other workspaces unexpectedly | M | Owner-only apply + audit log + provenance; org-admin gate is the tracked governance follow-up. |
| Gap scan floods review on huge schemas | M (Phase 2) | Cap proposals per scan; rank by apparent importance. |
| Reprocess on a missing on-disk file | L | Existing seed already skips missing files; preserve that guard. |

---

## Implementation Phases

<!--
  STATUS: pending | in-progress | complete
  PARALLEL: phases that can run concurrently
  DEPENDS: phases that must complete first
  PRP: link to generated plan file once created
-->

| # | Phase | Description | Status | Parallel | Depends | PRP Plan |
|---|-------|-------------|--------|----------|---------|----------|
| 1 | Proposal backbone | `schema_change_proposals` table + migration; `reprocess_document` service (promoted from seed); supersession + uniqueness guard | pending | - | - | - |
| 2 | Feature 1 backend | `propose_schema_for_document`, `apply_schema_proposal`; create/apply/reject endpoints; audit + claude_call_log wiring | pending | - | 1 | - |
| 3 | Feature 1 UI | "Generate Schema Draft" action, draft editor, apply/reject, reprocess trigger | pending | with 4 | 2 | - |
| 4 | Feature 2 backend | `propose_schema_extensions` gap-scan prompt + endpoint (reuses proposal table/services) | pending | with 3 | 2 | - |
| 5 | Feature 2 UI + hardening | "Suggested additions" surface; governance/notify-on-supersede polish; eval pass on proposal quality | pending | - | 3, 4 | - |

### Phase Details

**Phase 1: Proposal backbone** — *the non-negotiable foundation*
- **Goal**: The data + reprocess + versioning + validation substrate both features sit on.
- **Scope**: New `schema_change_proposals` table (with provenance + `draft|rejected|applied|failed` status) & Alembic migration (`/gen-migration`); **DB partial unique index** `UNIQUE(document_type, vertical) WHERE is_active=true`; atomic supersession helper + `get_schema_for_type` `order_by(version.desc())`; **`reprocess_document(document_id, schema_id, db)` with forced-schema path** (set schema_id + doc_type, skip re-detection); **`validate_proposal()` service** (names, types, thresholds, descriptions, normalized/collision-checked `document_type`). Tests for: supersession atomicity, the DB index rejecting a second active schema, forced reprocess, and each validation rule.
- **Success signal**: Inserting a v2 deactivates v1 atomically *and* the DB rejects a hand-crafted second active row; reprocessing a doc onto a forced schema yields `complete` without re-detection; invalid proposals are rejected by `validate_proposal` with a specific reason.

**Phase 2: Feature 1 backend**
- **Goal**: AI can draft a full schema from a `no_schema` doc and an **owner** can apply it via API.
- **Scope**: `propose_schema_for_document` (Claude prompt → `proposed_schema` + `proposed_fields` + `rationale`; **requires non-empty `ocr_text`, errors otherwise**; writes provenance); `apply_schema_proposal` (new-schema path; **calls `validate_proposal` first**); POST create-proposal, POST apply (**owner only**), POST reject; audit + claude_call_log.
- **Success signal**: TDD-covered round trip — unknown doc → proposal → owner apply → validated schema row exists & detectable; an OCR-empty doc returns a clear error instead of a hallucinated schema; an analyst is blocked from apply.

**Phase 3: Feature 1 UI**
- **Goal**: The whole MVP loop is doable in-app.
- **Scope**: "Generate Schema Draft" on a `no_schema` document; editable draft (field add/edit/remove, thresholds, parse_strategy); apply/reject; "Reprocess" button; status reflects `complete`.
- **Success signal**: Operator with no terminal access takes an unknown doc to `complete`.

**Phase 4: Feature 2 backend**
- **Goal**: Detect and propose out-of-scope fields on already-schema'd docs.
- **Scope**: `propose_schema_extensions(document_id, schema_id)` — scans OCR text + existing extractions, proposes additions with rationale; `apply_schema_proposal` extension path (full supersession → v2); endpoint.
- **Success signal**: A deed missing `notary_commission_expiration` yields a `schema_extension` proposal; approving it produces DEED v2 with the field.

**Phase 5: Feature 2 UI + hardening**
- **Goal**: Ship the gap-scan surface and close the rough edges.
- **Scope**: "Suggested schema additions" review UI; supersede-notify ("N docs on old version"); proposal-quality eval pass; governance decision applied if resolved.
- **Success signal**: Operator accepts selected suggested fields; metrics (acceptance rate) measurable.

### Parallelism Notes

Phases 3 and 4 can run concurrently: both depend only on Phase 2's proposal table + service contract. Phase 3 is frontend on the new-schema path; Phase 4 is backend on the extension path. They touch different layers and don't share state.

---

## Decisions Log

| Decision | Choice | Alternatives | Rationale |
|----------|--------|--------------|-----------|
| Mutation model | AI proposes, human approves, versioned apply | AI auto-edits active schemas | Prevents schema drift / unstable exports; correctness product. |
| Extension versioning | Full supersession (v2 replaces v1) | In-place append; decide later | Clean lineage; avoids `get_schema_for_type().first()` ambiguity. |
| Approval authority | **Apply: owner only. Draft/edit: analyst** | Owner-or-analyst (earlier pick, reversed) | Apply mutates global engine contract — that trust boundary belongs to owner. |
| Schema scope | Per-workspace proposals, global applied schemas | Workspace-scoped schemas; decide later | Matches current global schema model; defers tenancy rework. Org gate is a tracked follow-up. |
| Status lifecycle | `draft \| rejected \| applied \| failed` | `draft→approved→rejected→applied` | `approved` and `applied` overlapped; approval *is* the apply. Review tracked via `reviewed_by/at`. |
| Supersession enforcement | DB partial unique index | Test-enforced only | Survives future code paths, not just today's. |
| Proposal validation | First-class server-side gate on apply | Human review only | Review is necessary but not sufficient for an engine-contract change. |
| MVP boundary | Feature 1 before Feature 2 | Both at once | Feature 2 reuses Feature 1 infra; gap-scan is the riskier half. |
| Reprocess | Promote seed to a service method **with forced-schema path** | Reuse seed as-is | Seed re-runs detection and could re-classify a freshly-schema'd doc as `OTHER`. |

---

## Research Summary

**Codebase Context (grounded, with references)**
- `no_schema` status + auto-lead already exist: `document_pipeline.py:105` (`_no_schema`), enum at `models/document.py:41`, migration `c12f44824c55`.
- Schema-driven, call-time detection: `extraction_engine.py:90` (`_load_known_types`), `:203` (`get_schema_for_type`) — new schema rows go live without redeploy (ADR 0002).
- `DocumentSchema` has unused `version`/`is_active` columns (`models/document_schema.py:21-22`); every seed is `version=1, is_active=True` — no supersession logic exists.
- Reprocess routine: `seeds/reprocess_documents.py` (clear extractions → reset pending → `process_upload_background`).
- Human-in-loop review precedent: `routers/review.py` attempt-3 manual extractions that flip a doc to `complete` (`tests/test_schema_review.py`).
- Schema write surface absent: `routers/schemas.py` is read-only.
- Active guards that will shape implementation: `check_soft_delete.py`, `check_thin_routers.py`, ruff (per CLAUDE.md).

**Market Context**
- Not researched this pass (internal platform feature; codebase grounding prioritized). The pattern — schema/extraction-config inference with human approval and versioning — mirrors how IDP platforms (e.g. document-AI "auto-schema" + review queues) handle new document types. Worth a light competitive scan before Phase 5 if positioning matters.

---

*Generated: 2026-06-22*
*Status: DRAFT - needs validation*
