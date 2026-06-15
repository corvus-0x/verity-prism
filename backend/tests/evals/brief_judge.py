"""
LLM judge for brief evals (Claude, temperature 0 for reproducibility).

Two batched calls:
  judge_support(claims, evidence_by_id) -> list[bool]   # one per claim
  judge_coverage(facts, claims)         -> list[bool]   # one per fact
Strict JSON; raises on parse failure (a broken judge must fail loudly, not pass).
"""

import json

from app.services import claude_client
from app.services.claude_client import CHAT_MODEL
from app.utils.json_helpers import strip_json_fences

_JUDGE_TEMPERATURE = 0

_SUPPORT_SYSTEM = (
    "You are a strict evaluation judge. For each CLAIM, decide whether the cited "
    "EVIDENCE actually supports the claim's text. Judge only from the evidence "
    "given; if the evidence does not substantiate the claim, it is unsupported. "
    'Respond with JSON only: {"results": [true, false, ...]} with exactly one '
    "boolean per claim, in the same order."
)

_COVERAGE_SYSTEM = (
    "You are a strict evaluation judge. For each FACT, decide whether ANY of the "
    "CLAIMS asserts that fact (paraphrase counts; the claim must convey the same "
    'substance). Respond with JSON only: {"results": [true, false, ...]} with '
    "exactly one boolean per fact, in the same order."
)


def _call(system: str, payload: dict, expected: int) -> list:
    response = claude_client.get_client().messages.create(
        model=CHAT_MODEL,
        max_tokens=1024,
        temperature=_JUDGE_TEMPERATURE,
        system=system,
        messages=[{"role": "user", "content": json.dumps(payload)}],
    )
    parsed = json.loads(strip_json_fences(response.content[0].text))
    if "results" not in parsed:
        raise ValueError(f"Judge response missing 'results' key; got: {parsed!r}")
    results = [bool(x) for x in parsed["results"]]
    if len(results) != expected:
        raise ValueError(f"Judge returned {len(results)} results, expected {expected}")
    return results


def judge_support(claims: list[dict], evidence_by_id: dict) -> list[bool]:
    if not claims:
        return []
    items = []
    for c in claims:
        cited = [
            {"field": evidence_by_id[s].field_name, "value": evidence_by_id[s].field_value}
            for s in c.get("sources", [])
            if s in evidence_by_id
        ]
        items.append({"claim": c.get("text", ""), "evidence": cited})
    return _call(_SUPPORT_SYSTEM, {"claims": items}, expected=len(claims))


def judge_coverage(facts: list[str], claims: list[dict]) -> list[bool]:
    if not facts:
        return []
    payload = {"facts": facts, "claims": [c.get("text", "") for c in claims]}
    return _call(_COVERAGE_SYSTEM, payload, expected=len(facts))
