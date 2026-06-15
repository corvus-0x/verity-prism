"""
Synthesis service — the engine's post-extraction intelligence layer.

Turns a workspace's document_extractions into a grounded brief: a summary
plus structured claims, each citing the extraction rows it came from.
Commodity extractors stop at fields; this reads across documents.

Pipeline: _assemble_evidence (DB read + universal saliences) -> _synthesize
(one constrained Claude call that may cite only supplied evidence ids) ->
_validate_and_annotate (drop fabricated citations, attach grounding
confidence from the cited rows).
"""

import logging

from app.services.saliences import Evidence

logger = logging.getLogger(__name__)


def _validate_and_annotate(brief: dict, evidence: list[Evidence]) -> dict:
    """Drop claims that cite no valid evidence id, strip unknown ids from the
    rest, and annotate each surviving claim with grounding_confidence = the
    minimum confidence of its cited rows (so the brief can hedge weak claims).
    """
    by_id = {e.id: e for e in evidence}
    claims = []
    for claim in brief.get("claims", []) or []:
        sources = [s for s in (claim.get("sources") or []) if s in by_id]
        if not sources:
            continue  # unfalsifiable — a claim with no real citation is dropped
        claim["sources"] = sources
        claim["grounding_confidence"] = round(min(by_id[s].confidence for s in sources), 4)
        claims.append(claim)
    return {"summary": brief.get("summary", "") or "", "claims": claims}
