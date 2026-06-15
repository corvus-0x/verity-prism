# Synthesis Layer & Eval Harness — Design Spec

**Date:** 2026-06-15
**Status:** Draft — pending review
**Scope:** Add an engine-level **synthesis layer** that turns a workspace's structured extraction data into a grounded, readable *brief* (structured claims, each cited to source extraction rows), plus an **eval harness** that scores brief quality on faithfulness (precision) and completeness (recall). Domain-agnostic engine feature. Vertical signal rules are deferred and pluggable.

---

## 1. Why this exists — the IDP differentiator

Commodity document processors — AWS Textract, Azure Document Intelligence, Hyland — **stop at extraction**. They turn a document into fields and hand back a JSON blob. The reasoning that comes next — reading *across* documents, surfacing the outlier, catching that two filings disagree, flagging a missing required field, saying what it *means* — is left to the customer.

That gap is the product. Verity Prism's engine performs the **post-extraction reasoning** those platforms don't. The synthesis layer is the "Intelligent" in Intelligent Document Processing; everything before it is OCR with structure.

Crucially, this reasoning is only possible at the **workspace** level — treating a whole set of documents' `document_extractions` rows as one queryable corpus. Cross-document contradiction, outlier detection, missing-field flagging, and cross-document entity frequency cannot be produced at the single-document extraction layer the incumbents operate at. That cross-document intelligence is both the moat and the headline capability.

---

## 2. Design decisions (locked)

| # | Decision | Choice |
|---|----------|--------|
| 1 | Unit of synthesis | Whole workspace/case → one brief |
| 2 | Eval measures | Faithfulness (claim precision) + Completeness (signal recall) |
| 3 | Golden set | Hand-authored synthetic fixture workspaces |
| 4 | Brief contract | Structured claims, each with explicit citations to extraction rows |
| 5 | Generation | On-demand, persisted + versioned (auto-generate deferred) |
| 6 | Domain coupling | None. Engine reads only `document_extractions`. Cap rules pluggable via `signal_registry`, deferred |

---

## 3. Architecture

```
Document Sources → Ingestion → Extraction Pipeline → document_extractions
                                                            │
                                                            ▼
                                                  Synthesis Layer (NEW)
                                          _assemble_evidence → _synthesize → _validate_citations
                                                            │
                                                            ▼
                                                      briefs table (NEW)
                                                            │
                                                            ▼
                                               POST/GET /workspaces/{id}/brief
```

The synthesis layer is **engine** code. It never imports vertical logic. It synthesizes whatever lives in `document_extractions` for a workspace. *Which* signals matter beyond the universal saliences is cap configuration, registered through `signal_registry` (Section 8) and built incrementally — the engine and its eval harness never change when a cap adds a rule.

### Approach chosen — Constrained single-pass

The service pre-assembles a **citable evidence set** (the actual extraction rows). One structured Claude call sees *only* that set and may cite *only* IDs drawn from it. This makes faithfulness near-deterministic: a cited ID either exists in the evidence set or it doesn't (checked without an API call); only the semantic "does the source support the claim" step needs the judge.

Approaches rejected: a rules-first two-stage pipeline (bakes domain rules into the engine — wrong layer, and the rules aren't known yet) and agentic synthesis via the existing tool loop (non-deterministic, citations hard to pin, defeats eval-ability).

---

## 4. Components

Four new units, each independently testable. Routers stay thin; logic lives in the service.

### `backend/app/services/synthesis_service.py`
Public: `generate_brief(workspace_id, db) -> Brief`. Three internal steps:

- `_assemble_evidence(workspace_id, db) -> list[Evidence]` — pure DB read of `document_extractions` (joined to `documents` for filename/type) for the workspace. Each evidence item: `{id, document_id, filename, doc_type, field_name, field_value}`. **Only the universal IDP table** — no transactions/entities/findings (those are cap-flavored). Also computes the **universal saliences** (Section 5) over the evidence set.
- `_synthesize(evidence, saliences) -> dict` — one structured Claude call (reuses `claude_client` + per-call latency/token logging). Returns `{summary, claims:[{text, sources:[evidence_id…], signal_type, grounding_confidence}]}`. `grounding_confidence` is derived from the cited extraction rows' own confidence scores, so the brief can hedge claims that rest on shaky extractions — this is where the synthesis layer connects back to the per-field confidence layer it sits above. System prompt instructs: cite only provided IDs; do not assert anything not supported by the evidence.
- `_validate_citations(brief, evidence) -> brief` — deterministic guard: drop or flag any claim whose `sources` reference an ID absent from the evidence set, before persistence.

### `backend/app/models/brief.py`
ORM for the `briefs` table (Section 6).

### `backend/app/routers/briefs.py` (thin)
- `POST /workspaces/{id}/brief` — generate, persist next version, return it
- `GET  /workspaces/{id}/brief` — latest non-deleted version
- `GET  /workspaces/{id}/briefs` — version history

`audit.log()` is called after each generation (platform convention). Registered in `main.py`.

### Eval harness — `backend/tests/evals/`
`faithfulness.py`, `completeness.py` scorers; `fixtures/golden_workspaces/`; `test_brief_quality.py`. Detail in Section 7.

### Out of scope (noted follow-ups)
- Frontend "Case Brief" panel — this spec ends at the API.
- Auto-generation on pipeline events — deferred; requires this persistence layer underneath it first.

---

## 5. Universal saliences (the domain-agnostic intelligence)

Computed deterministically over the evidence set in `_assemble_evidence`. These are the cross-document facts a pure extractor cannot produce, and they are vertical-neutral:

- **Outlier value** — largest / anomalous numeric `field_value` across the set
- **Cross-document entity frequency** — a name/value appearing across the most documents
- **Missing required field** — a document missing a field its schema marks required (reuses the existing `not-extracted` state)
- **Contradiction** — same `field_name` with differing `field_value` across two documents
- **Coverage span** — the date range the document set spans
- **Chronology / event sequence** — documents ordered by their date fields into a timeline; surfaces *sequence* ("first X, then Y, then Z"), not just the span. Turning extractions into an ordered narrative is core synthesis value and fully domain-agnostic.
- **Duplicate / near-duplicate documents** — documents sharing a SHA-256 hash (already computed first in the pipeline) or near-identical key field values; e.g. "docs 3 and 7 are the same instrument." A pure extractor never surfaces this.

**Definition.** A *salience* is a notable cross-document fact the engine computes deterministically — the middle layer between raw data and judgment. Not "field X = 1250000" (data) and not "this is fraud" (cap judgment), but "this value is an outlier / these two documents disagree / this entity recurs."

Saliences are passed to `_synthesize` as candidate facts the brief should surface, and are the ground-truth checklist for the completeness eval. They make **no vertical assumptions** — the test for membership is: *can it be computed without knowing the vertical?* Outlier, contradiction, chronology, duplicate all pass; "below-appraisal" fails (only the fraud cap knows appraisal matters) and is therefore a cap detector, not a salience.

---

## 6. Data model

One new table, `briefs`, following versioned / observability / soft-delete conventions. One Alembic migration. No changes to existing tables.

| Column | Type | Notes |
|--------|------|-------|
| `id` | uuid PK | |
| `workspace_id` | uuid FK | scoped, indexed |
| `version` | int | increments per regeneration; prior rows retained |
| `summary` | text | human-readable lede |
| `claims` | jsonb | `[{text, sources:[extraction_id…], signal_type, grounding_confidence}]` — `grounding_confidence` derived from the cited rows' extraction confidence, letting the brief hedge claims built on low-confidence data |
| `model` | text | e.g. `claude-sonnet-4-6` — reproducibility |
| `latency_ms` | int | per-call observability (mirrors Claude call logging) |
| `input_tokens` | int | |
| `output_tokens` | int | |
| `generated_at` | timestamptz | |
| `is_deleted` | bool | soft-delete convention |
| `deleted_at` | timestamptz | |

`claims[].sources` holds `document_extractions.id` values — citations are real references into the central IDP table, so every claim is traceable to the exact extracted row.

---

## 7. Eval harness

Lives in `tests/evals/`, same shape and `@pytest.mark.eval` marker as `test_deed_extraction.py` (runs separately, hits the real Claude API).

### Fixtures — `tests/evals/fixtures/golden_workspaces/<case>/`
- `documents.json` — authored `document_extractions` rows. Seeds the evidence directly, **skipping OCR/extraction**, so the eval isolates *synthesis* quality from upstream extraction quality.
- `golden.json` — `must_surface` saliences (the planted facts) + `expected_clean: true|false` for negative controls.

Fixtures are generic document sets (mixed deeds/filings), **not** fraud cases. Each plants known saliences by construction — e.g. "largest amount is X", "entity Y appears in 3 docs", "doc 2 missing recording_date", "docs 1 and 3 disagree on grantor_name". At least one **negative control**: a clean set whose brief must invent nothing.

### Scorers (pure functions, unit-testable)
- `faithfulness.py` — two stages:
  1. **Deterministic** — every `claim.sources` ID exists in the seeded evidence set (catches fabricated citations with no API call).
  2. **LLM-as-judge** — for each claim, does the cited row's `field_value` support the claim text? Score = supported / total.
- `completeness.py` — of the `must_surface` saliences, how many did the brief's claims cover? Coverage is decided by **LLM-as-judge**: a salience is "covered" if any claim semantically asserts it (not string match, which would miss paraphrase). Score = surfaced / total. Negative-control cases assert the brief surfaces **zero** invented signals.

### `test_brief_quality.py`
Parametrized over fixtures; prints a per-case scorecard (✓/✗ per claim and per salience, like the deed eval); asserts faithfulness ≥ threshold and completeness ≥ threshold (thresholds set per-fixture).

---

## 8. Extension point — `signal_registry` (deferred, not built now)

Mirrors the existing `agent_registry` / `connector_registry` pattern. The engine ships with the universal saliences (Section 5). A vertical cap *registers* additional domain signal detectors over time (e.g., the fraud cap's "below-appraisal transfer" rule), keyed by vertical. `_assemble_evidence` merges any registered detectors' output into the candidate signals.

This is open/closed: the synthesis engine and eval harness are closed for modification; caps extend behavior by appending detectors. The rule set does not need to be known up front — detectors are added and implemented incrementally. **No detectors are implemented in this spec** beyond the universal saliences; only the registration seam is defined.

---

## 9. Testing

- **Unit (mocked Claude):** `_assemble_evidence` salience computation; `_validate_citations` drops bad citations; router scoping (a workspace's brief never includes another workspace's evidence IDs); versioning increments and retains history; soft-delete filtering.
- **Eval (real Claude, `@pytest.mark.eval`):** Section 7, run separately from the unit suite.
- **Scorer units:** `faithfulness` and `completeness` are pure functions tested directly against hand-built brief/evidence pairs (no API).

---

## 10. Build order (for the implementation plan)

1. `briefs` model + Alembic migration
2. `_assemble_evidence` + universal saliences (unit-tested, no Claude)
3. `_synthesize` + `_validate_citations` (mocked Claude unit tests)
4. `briefs` router + audit logging + `main.py` registration
5. Scorer pure functions + their unit tests
6. Golden fixtures + `test_brief_quality.py` eval
7. `signal_registry` seam (registration only; no cap detectors)
