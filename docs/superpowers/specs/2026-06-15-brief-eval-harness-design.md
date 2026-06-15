# Brief Eval Harness — Design Spec

**Date:** 2026-06-15
**Status:** Draft — pending review
**Scope:** A pytest-driven evaluation harness that measures the quality of `synthesize_brief` output on two axes — **faithfulness** (claim precision) and **completeness** (salience recall) — over hand-authored golden fixture workspaces, with a hybrid gate (deterministic hard asserts + LLM-judge measured scores under loose floors). This is **Plan 2** of the synthesis work; the synthesis layer (Plan 1) is merged to `main`.

**Depends on:** synthesis layer merged (`synthesize_brief`, `compute_saliences`, `Brief`). Parent spec: `2026-06-15-synthesis-layer-eval-harness-design.md` §7.

---

## 1. Purpose

The synthesis layer produces grounded briefs, but "is the brief good?" is currently a gut-check. This harness **measures** brief quality automatically so regressions are caught and quality is reportable — the "we measure output quality, not gut-check it" discipline.

It also doubles as the **test rig for the future Catalyst fraud rules** (cap detectors registered via `signal_registry`): "did the rule fire, and did the referral state it faithfully?" is exactly faithfulness + completeness. Build once; both products inherit the quality gate. (Catalyst fraud-flavored fixtures are out of scope here — this plan ships domain-neutral engine fixtures.)

---

## 2. Key design facts (read first)

`synthesize_brief` already runs `_validate_and_annotate`, which **drops any claim citing a non-existent extraction id** before returning. Consequences for the scorers:

- **Citation-existence is a guarantee, not a risk.** The eval still asserts it (every cited id ∈ seeded evidence) as a **regression guard** on the grounding backstop — it should always pass.
- **The real faithfulness risk is semantic:** a claim cites a *real* row whose value does not actually *support* the claim text. Only the LLM judge can catch this.
- **The negative control** (a benign fixture) checks that the brief invents **no** claims from data with nothing notable.

---

## 3. Hybrid gate model (decided)

| Check | Type | Effect |
|-------|------|--------|
| Every cited id exists in seeded evidence | Deterministic | Hard assert (guarantee regression guard) |
| `expected_clean` fixture → 0 claims | Deterministic | Hard assert (hallucination negative control) |
| Engine detection: planted salience type present in `compute_saliences` output | Deterministic | Hard assert (rule-fired guard) |
| Faithfulness (judge: claim supported by cited evidence) | LLM judge | Measured; assert ≥ loose floor (default 0.70) |
| Completeness — brief coverage (judge: must_surface fact asserted by a claim) | LLM judge | Measured; assert ≥ loose floor (default 0.60) |

Loose floors catch gross regressions without flaking on normal LLM-judge variance. Judge runs at **temperature 0** to minimize run-to-run wobble; floors absorb the residual.

---

## 4. Components

Five files under `backend/tests/evals/`, mirroring the existing `test_deed_extraction.py` pattern.

### `golden_briefs.py`
`GOLDEN_CASES`: a list of fixtures authored as **inline Python dicts**. Each fixture:

```python
{
    "id": "outlier_dupe_contradiction",
    "vertical": "general",
    "documents": [
        {"key": "deed1", "doc_type": "DEED", "sha256": "AAA", "uploaded_at": "2021-03-01"},
        # ...
    ],
    "extractions": [
        {"doc": "deed1", "field": "sale_amount", "value": "50000", "type": "currency", "confidence": 0.95},
        # ...
    ],
    "must_surface": [
        {"fact": "the $1,200,000 sale is the largest/outlier value", "salience_type": "outlier"},
        # ...
    ],
    "expected_clean": False,
    "thresholds": {"faithfulness": 0.70, "completeness": 0.60},
}
```

`documents[].key` is a fixture-local handle linking `extractions[].doc` to a document; the seeder maps it to a real generated document id. `must_surface[].salience_type` ties each expected fact to the detector that should produce it (enables the engine-detection layer).

### `brief_seeder.py`
`seed_fixture(fixture: dict, db) -> str`. Inserts a `User` (for FK), a `Workspace` (with `vertical`), the `Document` rows, and the `DocumentExtraction` rows (default `attempt=1`). Optionally a `DocumentSchema` with required fields when a fixture exercises `missing_field`. Uses `db.flush()` between parent/child inserts (autoflush=False + real FKs). Returns the `workspace_id`.

### `brief_judge.py`
The LLM judge (Claude, `CHAT_MODEL`, **temperature 0**). Two batched functions:

- `judge_support(claims, evidence_by_id) -> list[bool]` — one structured call: for each claim, do its cited rows' actual values support the claim text? Returns a per-claim supported flag.
- `judge_coverage(must_surface, claims) -> list[bool]` — one structured call: for each `must_surface` fact, does any claim assert it? Returns a per-fact covered flag.

Both return strict JSON; on a parse failure, fail the eval loudly (a broken judge must not silently pass). ~2 judge calls per fixture.

### `brief_scorers.py`
Pure orchestration over judge results + deterministic checks:

- `faithfulness(brief, evidence_by_id) -> (score, supported_flags)` — score = supported / total claims (1.0 if zero claims).
- `completeness(fixture, evidence, documents, brief) -> (engine_score, brief_score, detail)`:
  - **engine layer (deterministic):** run `compute_saliences(evidence, documents, required_by_doc)`; for each `must_surface` item, is a salience of its `salience_type` present? → engine_score.
  - **brief layer (judge):** `judge_coverage` → brief_score.
  - Both layers score **1.0 when `must_surface` is empty** (the negative-control case — nothing to recall, so recall is vacuously perfect; the "invented nothing" check is enforced separately by the `expected_clean` hard assert).
- `citation_integrity(brief, evidence_by_id) -> bool` — every cited id exists (guarantee guard).

### `test_brief_quality.py`
`@pytest.mark.eval`, parametrized over `GOLDEN_CASES`:

```
seed → synthesize_brief → 
  assert citation_integrity                          # hard
  if expected_clean: assert len(claims) == 0         # hard
  assert engine detection for each must_surface      # hard (rule fired)
  faith, _   = faithfulness(...)                     # measured
  eng, brf,_ = completeness(...)                     # measured
  print scorecard row
  assert faith >= thresholds.faithfulness            # loose floor
  assert brf   >= thresholds.completeness            # loose floor
```

Prints a per-fixture scorecard (✓/✗ per claim and per must_surface, like the deed eval). Writes `backend/tests/evals/results/brief_eval.json` (gitignored). A short `backend/tests/evals/README.md` documents how to run and shows a representative scorecard (the showable artifact).

---

## 5. Initial fixture set (4, domain-neutral)

1. **`outlier_dupe_contradiction`** — exercises outlier + entity_frequency + duplicate (two docs share a sha256) + contradiction + coverage_span.
2. **`chronology_missing_field`** — exercises chronology (dated events) + missing_field (a `DocumentSchema` with a required field left unextracted).
3. **`multi_doc_clean`** — negative control: several benign documents, `must_surface: []`, `expected_clean: True`.
4. **`single_doc_minimal`** — negative control: one document, ensures no invention on thin input.

Authored so the planted facts are known by construction. At least the two controls assert zero invented claims.

---

## 6. Running it

```bash
docker-compose run --rm \
  -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test \
  -e ANTHROPIC_API_KEY=sk-ant-... \
  backend pytest tests/evals/test_brief_quality.py -v -m eval
```

Excluded from CI exactly like `test_deed_extraction.py` (needs a live Claude key). The judge cost is ~2 calls/fixture × 4 fixtures + 4 synthesis calls ≈ low double digits per run.

---

## 7. Testing the harness itself

The judge and synthesis calls are real Claude (eval-gated), but the **pure** parts get ordinary unit tests (no API, run in normal CI):

- `brief_scorers.faithfulness` / `completeness` / `citation_integrity` against hand-built brief + evidence pairs (mocked judge results) — verify the arithmetic and the engine-detection layer.
- `brief_seeder.seed_fixture` against a small fixture — verify it produces a queryable workspace (FK ordering holds).

The judge functions themselves are exercised only under `-m eval`.

---

## 8. Out of scope (tracked elsewhere)

- **Catalyst fraud-rule fixtures** — come with the Catalyst cap work; reuse this harness.
- **Plan 3** (citation-resolve endpoint, ClaudeCallLog/metering wiring, dropped-citation logging) — separate.
- **Salience tuning** (outlier cross-field comparison, contradiction `doc_type=None`) — this harness is the instrument that will drive that tuning, but tuning changes are their own follow-ups.
- **Trend tracking / dashboards over eval runs** — future; `brief_eval.json` is the seed for it.

---

## 9. Build order (for the implementation plan)

1. `brief_seeder.py` + its unit test (no Claude).
2. `golden_briefs.py` — the 4 fixtures.
3. `brief_scorers.py` pure functions + unit tests (mocked judge results), including the engine-detection layer.
4. `brief_judge.py` — the two temp-0 batched judge calls.
5. `test_brief_quality.py` runner + scorecard + results JSON + `.gitignore` entry + `README.md`.
