import pytest
from app.services import audit as audit_service


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
