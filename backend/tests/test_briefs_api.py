import json
import uuid
from types import SimpleNamespace
from unittest.mock import patch

from app.models.document import Document
from app.models.document_extraction import DocumentExtraction
from app.models.workspace import Workspace, WorkspaceMember


def _fake_response(payload):
    return SimpleNamespace(
        content=[SimpleNamespace(text=json.dumps(payload))],
        usage=SimpleNamespace(input_tokens=5, output_tokens=7),
    )


def _seed(db, owner_user_id):
    ws = Workspace(id=str(uuid.uuid4()), name="Case", vertical="fraud", created_by=owner_user_id)
    db.add(ws)
    db.flush()
    db.add(WorkspaceMember(workspace_id=ws.id, user_id=owner_user_id, role="owner"))
    doc = Document(
        id=str(uuid.uuid4()),
        workspace_id=ws.id,
        filename="d.pdf",
        original_filename="d.pdf",
        file_path="/x",
        file_type="pdf",
        sha256_hash="H1",
        uploaded_by=owner_user_id,
        detected_doc_type="DEED",
    )
    db.add(doc)
    db.flush()
    db.add(
        DocumentExtraction(
            id="x1",
            document_id=doc.id,
            workspace_id=ws.id,
            field_name="sale_amount",
            field_value="500000",
            field_type="currency",
            confidence=0.8,
        )
    )
    db.commit()
    return ws


def _user_id(client, auth_headers):
    return client.get("/auth/me", headers=auth_headers).json()["id"]


@patch("app.services.claude_client.get_client")
def test_generate_and_get_latest_brief(mock_client, client, auth_headers, db):
    mock_client.return_value.messages.create.return_value = _fake_response(
        {
            "summary": "ok",
            "claims": [
                {"text": "sale 500000", "sources": ["x1"], "signal_type": "outlier"},
            ],
        }
    )
    ws = _seed(db, _user_id(client, auth_headers))

    gen = client.post(f"/workspaces/{ws.id}/brief", headers=auth_headers)
    assert gen.status_code == 200
    body = gen.json()
    assert body["version"] == 1
    assert body["claims"][0]["sources"] == ["x1"]
    assert body["claims"][0]["grounding_confidence"] == 0.8

    latest = client.get(f"/workspaces/{ws.id}/brief", headers=auth_headers)
    assert latest.status_code == 200
    assert latest.json()["version"] == 1


@patch("app.services.claude_client.get_client")
def test_regenerate_increments_version_and_history(mock_client, client, auth_headers, db):
    mock_client.return_value.messages.create.return_value = _fake_response(
        {"summary": "ok", "claims": []}
    )
    ws = _seed(db, _user_id(client, auth_headers))

    client.post(f"/workspaces/{ws.id}/brief", headers=auth_headers)
    client.post(f"/workspaces/{ws.id}/brief", headers=auth_headers)

    history = client.get(f"/workspaces/{ws.id}/briefs", headers=auth_headers)
    assert history.status_code == 200
    versions = [b["version"] for b in history.json()["briefs"]]
    assert versions == [2, 1]  # newest first


def test_latest_brief_404_when_none(client, auth_headers, db):
    ws = _seed(db, _user_id(client, auth_headers))
    resp = client.get(f"/workspaces/{ws.id}/brief", headers=auth_headers)
    assert resp.status_code == 404


def test_brief_requires_membership(client, auth_headers, db):
    # workspace exists but has NO WorkspaceMember row for this user
    ws = Workspace(
        id=str(uuid.uuid4()),
        name="Foreign",
        vertical="fraud",
        created_by=_user_id(client, auth_headers),
    )
    db.add(ws)
    db.commit()
    resp = client.post(f"/workspaces/{ws.id}/brief", headers=auth_headers)
    assert resp.status_code == 404
