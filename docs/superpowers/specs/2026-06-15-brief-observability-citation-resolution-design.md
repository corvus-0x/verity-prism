# Brief Observability & Citation Resolution — Design Note

**Date:** 2026-06-15
**Status:** Backlog — design note for the next plan (follow-up to PR #8, the synthesis layer)
**Depends on:** `feat/synthesis-layer` (PR #8) merged. Spec: `2026-06-15-synthesis-layer-eval-harness-design.md`.

---

## Why this exists

PR #8 shipped the synthesis layer: workspace briefs with structured claims, each carrying a `sources` array of real `document_extractions.id` values plus a `grounding_confidence`. The brief is **stored and correct**, but three gaps keep it from being *traceable and observable* — the properties that make a brief trustworthy to an operator and measurable as a system.

This note captures those three workstreams so they aren't lost. It is a design note, not yet a TDD plan — it should be brainstormed into a plan when picked up.

**Plan ordering:** Eval harness (faithfulness + completeness) is **Plan 2** and is independent. This is effectively **Plan 3**. They can be built in either order; #3 (dropped-citation logging) produces a signal Plan 2 can consume.

---

## Workstream 1 — Citation resolution (highest value)

**Problem.** The brief API returns `claims[].sources` as raw `document_extractions.id` strings. There is no way for a client to turn a citation into something an operator can inspect. The data exists — each id resolves to a row with `document_id`, `field_name`, `field_value`, and an `evidence` JSONB holding the base64 PNG region capture (PDF crop + page + bounding box) from the review-pane feature — but nothing surfaces it.

**Build.** A read endpoint that resolves a citation to its source:
- `GET /workspaces/{workspace_id}/brief/citations/{extraction_id}` → `{document_id, filename, doc_type, field_name, field_value, confidence, evidence}` (evidence = the region-capture JSON when present).
- Membership-gated via `get_workspace_or_404`; the extraction must belong to the workspace (scope check — never resolve a citation to another workspace's row).
- Consider a batch variant (`POST .../brief/citations` with a list of ids) so a brief with many claims resolves in one round-trip.

**Result.** "Click a claim → jump to the highlighted source on the page" becomes possible. This is the trust mechanism for the deferred frontend "Case Brief" panel, which consumes this endpoint.

**Note on snapshots.** Briefs cite the latest-attempt row at generation time and are versioned snapshots. A later correction does not rewrite an old brief; regenerate to get a new version. The resolve endpoint should resolve the *cited* row id directly (not "latest for that field"), preserving the snapshot.

---

## Workstream 2 — Synthesis observability (ClaudeCallLog + metering)

**Problem.** `extraction_engine._log_claude_call()` writes a `ClaudeCallLog` row (`call_type`, latency, tokens) for every Claude call, which feeds the observability dashboard and `metering.py`. `synthesis_service._synthesize()` writes **no** ClaudeCallLog row — it only stuffs latency/tokens onto the brief. So synthesis spend and latency are **invisible** to the dashboard and to metering.

**Build.**
- In `_synthesize` (or `synthesize_brief`), write a `ClaudeCallLog` row with `call_type="brief_synthesis"`, capturing latency, input/output tokens, document/workspace context — matching the extraction-engine pattern.
- Confirm `metering.py` picks up the new call_type (cost rollups).
- Verify the observability router/dashboard surfaces the new call_type (may need a label).

**Result.** Synthesis is observable and costed like every other Claude call.

---

## Workstream 3 — Dropped-citation logging (feeds the eval harness)

**Problem.** When `_validate_and_annotate` drops a claim that cited a non-existent extraction id (a hallucinated citation), it happens silently. That dropped count is a live **faithfulness signal** — exactly what the eval harness (Plan 2) wants — and it is currently discarded.

**Build.**
- Have `_validate_and_annotate` (or its caller) count claims dropped for invalid citations and citations stripped from surviving claims.
- Log it per generation (structured log + ideally a field on the audit `after_state` and/or the ClaudeCallLog row from Workstream 2): e.g. `{"claims_total": N, "claims_dropped_invalid_citation": k}`.
- Optional: persist a small `synthesis_quality` record or fold into the brief row so the eval harness and dashboard can trend it over time.

**Result.** A live, per-generation faithfulness signal — and a real metric to trend, not just a test-time number.

---

## Out of scope here (tracked elsewhere)
- **Eval harness** (faithfulness + completeness scorers, golden fixtures) — Plan 2.
- **Frontend "Case Brief" panel** — consumes Workstream 1.
- **Brief-level human corrections** — deliberately not planned. Current model: correct upstream (fix the extraction → regenerate). Revisit only if operators need a claim-level dismiss/flag affordance.
- **Auto-generation on pipeline events** — future; needs the persistence layer (now shipped) underneath it.
- **Salience tuning** (outlier cross-field comparison, contradiction `doc_type=None` grouping) — to be driven by the Plan 2 eval harness.
