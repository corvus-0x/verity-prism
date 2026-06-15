"""
Brief quality eval — runs synthesize_brief over golden fixtures and scores
faithfulness + completeness. Real Claude (synthesis + judge); run separately:

    docker-compose run --rm \
        -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test \
        -e ANTHROPIC_API_KEY=sk-ant-... \
        backend pytest tests/evals/test_brief_quality.py -v -m eval

Hybrid gate: deterministic checks are hard asserts; judge scores are measured
and asserted only against the per-fixture loose floors.
"""

import json
import os

import pytest

from app.services.synthesis_service import _assemble_evidence, synthesize_brief
from tests.evals.brief_judge import judge_coverage, judge_support
from tests.evals.brief_scorers import citation_integrity, completeness, faithfulness
from tests.evals.brief_seeder import seed_fixture
from tests.evals.golden_briefs import GOLDEN_CASES

_RESULTS: list[dict] = []


@pytest.mark.eval
@pytest.mark.parametrize("fixture", GOLDEN_CASES, ids=[f["id"] for f in GOLDEN_CASES])
def test_brief_quality(fixture, db):
    ws_id = seed_fixture(fixture, db)
    brief = synthesize_brief(ws_id, db)

    evidence, documents, required = _assemble_evidence(ws_id, db)
    evidence_by_id = {e.id: e for e in evidence}

    # HARD: grounding guarantee — a stored claim can never cite a fake id.
    assert citation_integrity(brief, evidence_by_id), (
        f"{fixture['id']}: brief cites a non-existent evidence id"
    )

    # HARD: hallucination negative control.
    # NOTE: this asserts a clean fixture invents NO claims. If this proves
    # brittle (the model emits a benign, faithful restatement on clean input),
    # relax to: assert all(c.get("signal_type", "general") == "general"
    #                       for c in brief["claims"]) — i.e. no INVENTED saliences.
    if fixture.get("expected_clean"):
        assert len(brief["claims"]) == 0, (
            f"{fixture['id']}: clean fixture should invent no claims, got {len(brief['claims'])}"
        )

    # MEASURED.
    faith, _ = faithfulness(brief, evidence_by_id, judge_support)
    eng, brf, detail = completeness(
        fixture.get("must_surface", []),
        evidence,
        documents,
        required,
        fixture.get("vertical", "general"),
        brief,
        judge_coverage,
    )

    # HARD: every planted salience must be detected by the engine (rule fired).
    for m, fired in zip(fixture.get("must_surface", []), detail["engine"]):
        assert fired, f"{fixture['id']}: engine did not detect salience '{m['salience_type']}'"

    print(f"\n── {fixture['id']} ──")
    print(
        f"  claims={len(brief['claims'])}  faithfulness={faith:.2f}  "
        f"completeness(brief)={brf:.2f}  completeness(engine)={eng:.2f}"
    )
    _RESULTS.append(
        {
            "id": fixture["id"],
            "claims": len(brief["claims"]),
            "faithfulness": round(faith, 3),
            "completeness_brief": round(brf, 3),
            "completeness_engine": round(eng, 3),
        }
    )

    th = fixture.get("thresholds", {})
    assert faith >= th.get("faithfulness", 0.70), (
        f"{fixture['id']}: faithfulness {faith:.2f} below floor {th.get('faithfulness', 0.70)}"
    )
    assert brf >= th.get("completeness", 0.60), (
        f"{fixture['id']}: completeness {brf:.2f} below floor {th.get('completeness', 0.60)}"
    )


def teardown_module(module):
    """Write the accumulated scorecard to results/brief_eval.json (gitignored)."""
    if not _RESULTS:
        return
    out_dir = os.path.join(os.path.dirname(__file__), "results")
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "brief_eval.json"), "w") as f:
        json.dump(_RESULTS, f, indent=2)
