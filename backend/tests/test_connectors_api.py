"""Connectors API router tests — list/search/fetch."""
from unittest.mock import patch

import pytest

from app.models.workspace import Workspace
from app.services.connectors.base import SearchCandidate


@pytest.fixture
def workspace(client, auth_headers, db):
    """Create a workspace via the API (so the authed user is a member) and
    return the persisted ORM object (vertical defaults to 'general')."""
    ws_id = client.post(
        "/workspaces/",
        json={"name": "Connector Test", "vertical": "general"},
        headers=auth_headers,
    ).json()["id"]
    return db.query(Workspace).filter(Workspace.id == ws_id).first()


def test_list_connectors_for_workspace(client, auth_headers, workspace):
    r = client.get(f"/workspaces/{workspace.id}/connectors", headers=auth_headers)
    assert r.status_code == 200
    ids = {c["id"] for c in r.json()}
    assert "irs-teos" in ids


def test_search_endpoint_returns_candidates(client, auth_headers, workspace):
    fake = [SearchCandidate(ref="123456789", display_name="Bright Future Ministries Inc",
                            identifier="12-3456789", location="Marysville, OH")]
    with patch("app.routers.connectors.connector_registry.get_connector") as gc:
        gc.return_value.search.return_value = fake
        r = client.post(
            f"/workspaces/{workspace.id}/connectors/irs-teos/search",
            json={"params": {"query": "Bright Future"}}, headers=auth_headers,
        )
    assert r.status_code == 200
    assert r.json()[0]["display_name"] == "Bright Future Ministries Inc"


def test_fetch_creates_run_and_returns_running(client, auth_headers, workspace):
    with patch("app.routers.connectors.BackgroundTasks.add_task"):
        r = client.post(
            f"/workspaces/{workspace.id}/connectors/irs-teos/fetch",
            json={"candidate_ref": "123456789", "candidate_label": "Bright Future",
                  "search_query": "Bright Future", "item_refs": ["123456789:2023:obj"]},
            headers=auth_headers,
        )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "running"
    assert "run_id" in body
