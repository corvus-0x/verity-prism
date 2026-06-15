from app.services.saliences import Evidence
from tests.evals.brief_scorers import citation_integrity, completeness, faithfulness


def _ev(id, field="sale_amount", value="100", ftype="currency", doc="d1"):
    return Evidence(
        id=id,
        document_id=doc,
        filename="f.pdf",
        doc_type="DEED",
        field_name=field,
        field_value=value,
        field_type=ftype,
    )


def test_citation_integrity_detects_fake_id():
    assert (
        citation_integrity(
            {"claims": [{"text": "x", "sources": ["e1", "ghost"]}]}, {"e1": _ev("e1")}
        )
        is False
    )
    assert (
        citation_integrity({"claims": [{"text": "x", "sources": ["e1"]}]}, {"e1": _ev("e1")})
        is True
    )


def test_faithfulness_fraction_supported():
    brief = {"claims": [{"text": "a", "sources": ["e1"]}, {"text": "b", "sources": ["e2"]}]}
    score, flags = faithfulness(
        brief, {"e1": _ev("e1"), "e2": _ev("e2")}, judge_support=lambda claims, ev: [True, False]
    )
    assert score == 0.5 and flags == [True, False]


def test_faithfulness_empty_claims_is_one():
    score, flags = faithfulness({"claims": []}, {}, judge_support=lambda c, e: [])
    assert score == 1.0 and flags == []


def test_completeness_engine_layer_fires_for_outlier():
    evidence = [_ev("e1", value="1200000", doc="d1"), _ev("e2", value="50000", doc="d2")]
    must = [{"fact": "the 1.2M sale is the outlier", "salience_type": "outlier"}]
    brief = {"claims": [{"text": "the $1.2M sale is largest", "sources": ["e1"]}]}
    eng, brf, detail = completeness(
        must, evidence, [], {}, "general", brief, judge_coverage=lambda facts, claims: [True]
    )
    assert eng == 1.0
    assert brf == 1.0
    assert detail["engine"] == [True]


def test_completeness_engine_layer_misses_absent_salience():
    evidence = [_ev("e1", value="100", doc="d1")]
    must = [{"fact": "outlier", "salience_type": "outlier"}]
    eng, brf, detail = completeness(
        must, evidence, [], {}, "general", {"claims": []}, judge_coverage=lambda f, c: [False]
    )
    assert eng == 0.0
    assert detail["engine"] == [False]


def test_completeness_empty_must_surface_is_one():
    eng, brf, detail = completeness(
        [], [], [], {}, "general", {"claims": []}, judge_coverage=lambda f, c: []
    )
    assert eng == 1.0 and brf == 1.0
