import uuid
import pytest
from app.models.audit import AuditLog
from app.models.document import Document
from app.models.user import User
from app.models.workspace import Workspace
from app.services import audit as audit_service
from app.services.document_pipeline import _fail


@pytest.fixture
def workspace_id(client, auth_headers):
    return client.post(
        "/workspaces/", json={"name": "Audit Test"}, headers=auth_headers
    ).json()["id"]


def test_audit_log_returns_paginated_entries(client, auth_headers, workspace_id, db):
    audit_service.log(
        db,
        action="uploaded",
        workspace_id=workspace_id,
        entity_type="document",
        entity_id="doc-abc",
        after_state={"filename": "test.pdf"},
    )

    response = client.get(
        f"/workspaces/{workspace_id}/audit-log?page=1&limit=50",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert "entries" in data
    assert "total" in data
    assert "pages" in data
    assert data["total"] >= 1
    actions = [e["action"] for e in data["entries"]]
    assert "uploaded" in actions


def test_audit_log_scoped_to_workspace(client, auth_headers, workspace_id, db):
    other_ws = client.post(
        "/workspaces/", json={"name": "Other"}, headers=auth_headers
    ).json()["id"]
    audit_service.log(db, action="searched", workspace_id=other_ws)
    audit_service.log(
        db,
        action="uploaded",
        workspace_id=workspace_id,
        entity_type="document",
        entity_id="doc-xyz",
    )

    response = client.get(
        f"/workspaces/{workspace_id}/audit-log?page=1&limit=50",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    actions = [e["action"] for e in data["entries"]]
    assert "searched" not in actions
    assert "uploaded" in actions


# ── M4a: pipeline failure audit ─────────────────────────────────────────────

@pytest.fixture
def user_ws_doc(db):
    user = User(
        id=str(uuid.uuid4()),
        email="pipeline_test@example.com",
        password_hash="hashed",
        full_name="Test User",
    )
    db.add(user)
    ws = Workspace(
        id=str(uuid.uuid4()),
        name="Test WS",
        vertical="fraud",
        created_by=user.id,
    )
    db.add(ws)
    db.flush()
    doc = Document(
        id=str(uuid.uuid4()),
        workspace_id=ws.id,
        filename="test.pdf",
        original_filename="test.pdf",
        file_path="/tmp/test.pdf",
        file_type="pdf",
        sha256_hash="a" * 64,
        uploaded_by=user.id,
        extraction_status="pending",
    )
    db.add(doc)
    db.commit()
    return user, ws, doc


def test_fail_writes_upload_failed_audit_row(db, user_ws_doc):
    user, ws, doc = user_ws_doc

    _fail(doc, "OCR failed: corrupted file", db)

    entry = (
        db.query(AuditLog)
        .filter(AuditLog.action == "upload_failed", AuditLog.entity_id == doc.id)
        .first()
    )
    assert entry is not None
    assert entry.user_id == user.id
    assert entry.workspace_id == ws.id
    assert "OCR failed" in entry.after_state["error"]
