"""
Brief eval scorers. Deterministic checks are pure; judged checks take an
injected judge function so the scorers unit-test without Claude.

  citation_integrity(brief, evidence_by_id) -> bool          # grounding guarantee guard
  faithfulness(brief, evidence_by_id, judge_support) -> (score, flags)
  completeness(must_surface, evidence, documents, required_by_doc, vertical,
               brief, judge_coverage) -> (engine_score, brief_score, detail)
"""

from app.services import signal_registry
from app.services.saliences import compute_saliences


def citation_integrity(brief: dict, evidence_by_id: dict) -> bool:
    """True iff every cited source id in every claim exists in the evidence set."""
    for claim in brief.get("claims", []):
        for src in claim.get("sources", []):
            if src not in evidence_by_id:
                return False
    return True


def faithfulness(brief: dict, evidence_by_id: dict, judge_support):
    """Fraction of claims whose cited evidence supports the claim text.
    judge_support(claims, evidence_by_id) -> list[bool], one per claim.
    Returns (score, per-claim flags). Score is 1.0 when there are no claims.
    """
    claims = brief.get("claims", [])
    if not claims:
        return 1.0, []
    flags = judge_support(claims, evidence_by_id)
    score = sum(1 for f in flags if f) / len(flags)
    return score, flags


def completeness(
    must_surface, evidence, documents, required_by_doc, vertical, brief, judge_coverage
):
    """Two layers of recall over the planted must_surface facts:
      engine_score: fraction whose salience_type is produced by compute_saliences
                    over the evidence (did the detector fire?).
      brief_score:  fraction asserted by some claim (judge).
    Both are 1.0 when must_surface is empty (negative control — nothing to recall).
    Returns (engine_score, brief_score, detail{engine:[bool], brief:[bool]}).
    """
    if not must_surface:
        return 1.0, 1.0, {"engine": [], "brief": []}

    saliences = compute_saliences(
        evidence, documents, required_by_doc, signal_registry.get_detectors(vertical)
    )
    present_types = {s.type for s in saliences}
    engine_flags = [m["salience_type"] in present_types for m in must_surface]
    engine_score = sum(1 for f in engine_flags if f) / len(must_surface)

    brief_flags = judge_coverage([m["fact"] for m in must_surface], brief.get("claims", []))
    if len(brief_flags) != len(must_surface):
        raise ValueError(
            f"judge_coverage returned {len(brief_flags)} flags, expected {len(must_surface)}"
        )
    brief_score = (sum(1 for f in brief_flags if f) / len(brief_flags)) if brief_flags else 0.0
    return engine_score, brief_score, {"engine": engine_flags, "brief": brief_flags}
