from app.services.saliences import Evidence
from app.services.synthesis_service import _validate_and_annotate


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


import json
import uuid
from types import SimpleNamespace
from unittest.mock import patch

from app.models.brief import Brief
from app.models.document import Document
from app.models.document_extraction import DocumentExtraction
from app.models.user import User
from app.models.workspace import Workspace
from app.services.synthesis_service import store_brief, synthesize_brief


def _fake_response(payload: dict):
    return SimpleNamespace(
        content=[SimpleNamespace(text=json.dumps(payload))],
        usage=SimpleNamespace(input_tokens=11, output_tokens=22),
    )


def _seed_workspace(db):
    # FKs are enforced (real Postgres) — create a User for created_by/uploaded_by.
    user = User(
        id=str(uuid.uuid4()),
        email=f"{uuid.uuid4()}@example.com",
        password_hash="x",
        full_name="Seed User",
    )
    db.add(user)
    db.flush()  # make user.id visible to FK checks before dependents are inserted
    ws = Workspace(id=str(uuid.uuid4()), name="Case A", vertical="fraud", created_by=user.id)
    db.add(ws)
    db.flush()  # make ws.id visible before Document FK resolves
    doc = Document(
        id=str(uuid.uuid4()),
        workspace_id=ws.id,
        filename="deed1.pdf",
        original_filename="deed1.pdf",
        file_path="/x",
        file_type="pdf",
        sha256_hash="HASH1",
        uploaded_by=user.id,
        detected_doc_type="DEED",
    )
    db.add(doc)
    ext = DocumentExtraction(
        id="ext-1",
        document_id=doc.id,
        workspace_id=ws.id,
        field_name="sale_amount",
        field_value="1250000",
        field_type="currency",
        confidence=0.9,
    )
    db.add(ext)
    db.commit()
    return ws, doc, ext


@patch("app.services.claude_client.get_client")
def test_synthesize_brief_end_to_end(mock_get_client, db):
    ws, doc, ext = _seed_workspace(db)
    mock_get_client.return_value.messages.create.return_value = _fake_response(
        {
            "summary": "One deed.",
            "claims": [
                {"text": "Sale was 1,250,000", "sources": ["ext-1"], "signal_type": "outlier"},
                {"text": "hallucinated", "sources": ["ghost"], "signal_type": "general"},
            ],
        }
    )

    brief = synthesize_brief(ws.id, db)

    assert brief["summary"] == "One deed."
    assert [c["text"] for c in brief["claims"]] == ["Sale was 1,250,000"]  # ghost dropped
    assert brief["claims"][0]["grounding_confidence"] == 0.9
    assert brief["model"]  # set from CHAT_MODEL
    assert brief["input_tokens"] == 11 and brief["output_tokens"] == 22
    assert brief["latency_ms"] is not None


@patch("app.services.claude_client.get_client")
def test_store_brief_versions_increment(mock_get_client, db):
    ws, _, _ = _seed_workspace(db)
    b1 = store_brief(ws.id, {"summary": "v1", "claims": []}, db)
    b2 = store_brief(ws.id, {"summary": "v2", "claims": []}, db)
    assert b1.version == 1 and b2.version == 2
    assert db.query(Brief).filter(Brief.workspace_id == ws.id).count() == 2
