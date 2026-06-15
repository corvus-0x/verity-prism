from app.services.synthesis_service import _validate_and_annotate

from app.services.saliences import Evidence


def _ev(id, conf=1.0):
    return Evidence(
        id=id,
        document_id="d1",
        filename="d.pdf",
        doc_type="DEED",
        field_name="f",
        field_value="v",
        field_type="text",
        confidence=conf,
    )


def test_validate_drops_claims_with_no_valid_citation():
    evidence = [_ev("e1")]
    raw = {
        "summary": "s",
        "claims": [
            {"text": "valid", "sources": ["e1"], "signal_type": "general"},
            {"text": "fabricated", "sources": ["does-not-exist"], "signal_type": "general"},
            {"text": "uncited", "sources": [], "signal_type": "general"},
        ],
    }
    out = _validate_and_annotate(raw, evidence)
    texts = [c["text"] for c in out["claims"]]
    assert texts == ["valid"]
    assert out["summary"] == "s"


def test_validate_filters_unknown_ids_but_keeps_valid_ones():
    evidence = [_ev("e1"), _ev("e2")]
    raw = {
        "summary": "",
        "claims": [
            {"text": "mixed", "sources": ["e1", "ghost", "e2"], "signal_type": "general"},
        ],
    }
    out = _validate_and_annotate(raw, evidence)
    assert out["claims"][0]["sources"] == ["e1", "e2"]


def test_grounding_confidence_is_min_of_cited_rows():
    evidence = [_ev("e1", conf=0.95), _ev("e2", conf=0.40)]
    raw = {
        "summary": "",
        "claims": [
            {"text": "c", "sources": ["e1", "e2"], "signal_type": "general"},
        ],
    }
    out = _validate_and_annotate(raw, evidence)
    assert out["claims"][0]["grounding_confidence"] == 0.4


def test_validate_handles_missing_keys_gracefully():
    out = _validate_and_annotate({}, [])
    assert out == {"summary": "", "claims": []}
