from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.services.saliences import Evidence
from tests.evals.brief_judge import judge_coverage, judge_support


def _resp(text):
    return SimpleNamespace(content=[SimpleNamespace(text=text)])


@patch("app.services.claude_client.get_client")
def test_judge_support_parses_results_and_uses_temp_0(mock_client):
    mock_client.return_value.messages.create.return_value = _resp('{"results": [true, false]}')
    ev = {
        "e1": Evidence(
            id="e1",
            document_id="d",
            filename="f",
            doc_type="DEED",
            field_name="amt",
            field_value="100",
            field_type="currency",
        )
    }
    claims = [{"text": "a", "sources": ["e1"]}, {"text": "b", "sources": ["e1"]}]

    assert judge_support(claims, ev) == [True, False]
    kwargs = mock_client.return_value.messages.create.call_args.kwargs
    assert kwargs["temperature"] == 0


@patch("app.services.claude_client.get_client")
def test_judge_coverage_parses_results(mock_client):
    mock_client.return_value.messages.create.return_value = _resp('{"results": [true]}')
    assert judge_coverage(["a fact"], [{"text": "a claim"}]) == [True]


def test_judge_support_no_claims_makes_no_call():
    assert judge_support([], {}) == []


def test_judge_coverage_no_facts_makes_no_call():
    assert judge_coverage([], [{"text": "x"}]) == []


@patch("app.services.claude_client.get_client")
def test_judge_support_raises_on_length_mismatch(mock_client):
    mock_client.return_value.messages.create.return_value = _resp('{"results": [true]}')
    ev = {
        "e1": Evidence(
            id="e1",
            document_id="d",
            filename="f",
            doc_type="DEED",
            field_name="amt",
            field_value="100",
            field_type="currency",
        )
    }
    claims = [{"text": "a", "sources": ["e1"]}, {"text": "b", "sources": ["e1"]}]
    with pytest.raises(ValueError, match="expected 2"):
        judge_support(claims, ev)


@patch("app.services.claude_client.get_client")
def test_judge_coverage_raises_on_missing_results_key(mock_client):
    mock_client.return_value.messages.create.return_value = _resp('{"summary": "nope"}')
    with pytest.raises(ValueError, match="missing 'results' key"):
        judge_coverage(["a fact"], [{"text": "a claim"}])
