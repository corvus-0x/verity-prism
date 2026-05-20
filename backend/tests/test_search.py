import pytest
from unittest.mock import patch, MagicMock


@pytest.fixture
def workspace_id(client, auth_headers):
    return client.post("/workspaces/", json={"name": "Test"},
                       headers=auth_headers).json()["id"]


def test_search_endpoint_exists(client, auth_headers, workspace_id):
    with patch("app.services.search_service.Anthropic") as mock_anthropic:
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client
        mock_client.messages.create.return_value = MagicMock(
            content=[MagicMock(text='{"fts_query": "deed", "field_filters": [], "doc_type_filter": null}')]
        )
        response = client.post(
            f"/workspaces/{workspace_id}/search",
            json={"query": "find all deeds"},
            headers=auth_headers,
        )
    assert response.status_code == 200
    assert "results" in response.json()
    assert "query" in response.json()


def test_empty_workspace_returns_empty_results(client, auth_headers, workspace_id):
    with patch("app.services.search_service.Anthropic") as mock_anthropic:
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client
        mock_client.messages.create.return_value = MagicMock(
            content=[MagicMock(text='{"fts_query": "anything", "field_filters": [], "doc_type_filter": null}')]
        )
        response = client.post(
            f"/workspaces/{workspace_id}/search",
            json={"query": "anything"},
            headers=auth_headers,
        )
    assert response.status_code == 200
    assert response.json()["results"] == []


def test_search_is_audit_logged(client, auth_headers, workspace_id, db):
    from app.models.audit import AuditLog
    with patch("app.services.search_service.Anthropic") as mock_anthropic:
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client
        mock_client.messages.create.return_value = MagicMock(
            content=[MagicMock(text='{"fts_query": "test", "field_filters": [], "doc_type_filter": null}')]
        )
        client.post(
            f"/workspaces/{workspace_id}/search",
            json={"query": "test search"},
            headers=auth_headers,
        )
    log_entry = db.query(AuditLog).filter(AuditLog.action == "searched").first()
    assert log_entry is not None
