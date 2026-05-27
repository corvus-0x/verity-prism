import pytest
from unittest.mock import patch, MagicMock


@pytest.fixture
def workspace_id(client, auth_headers):
    return client.post(
        "/workspaces/",
        json={"name": "Test Workspace", "vertical": "fraud"},
        headers=auth_headers,
    ).json()["id"]


def _mock_end_turn(text: str) -> MagicMock:
    """Build a mock Claude response that ends immediately with text."""
    block = MagicMock()
    block.type = "text"
    block.text = text
    response = MagicMock()
    response.stop_reason = "end_turn"
    response.content = [block]
    return response


def test_create_conversation(client, auth_headers, workspace_id):
    response = client.post(
        f"/workspaces/{workspace_id}/conversations", headers=auth_headers
    )
    assert response.status_code == 201
    assert response.json()["workspace_id"] == workspace_id


def test_send_message_returns_assistant_response(client, auth_headers, workspace_id):
    conv = client.post(
        f"/workspaces/{workspace_id}/conversations", headers=auth_headers
    ).json()

    with patch("app.services.ai_engine.client") as mock_client:
        mock_client.messages.create.return_value = _mock_end_turn(
            "Based on the workspace data, I found relevant records."
        )
        response = client.post(
            f"/workspaces/{workspace_id}/conversations/{conv['id']}/messages",
            json={"content": "What documents are in this workspace?"},
            headers=auth_headers,
        )

    assert response.status_code == 201
    data = response.json()
    assert data["role"] == "assistant"
    assert len(data["content"]) > 0


def test_conversation_title_set_from_first_message(client, auth_headers, workspace_id):
    conv = client.post(
        f"/workspaces/{workspace_id}/conversations", headers=auth_headers
    ).json()
    assert conv["title"] is None

    with patch("app.services.ai_engine.client") as mock_client:
        mock_client.messages.create.return_value = _mock_end_turn("Here is what I found.")
        client.post(
            f"/workspaces/{workspace_id}/conversations/{conv['id']}/messages",
            json={"content": "What entities are in this workspace?"},
            headers=auth_headers,
        )

    updated = client.get(
        f"/workspaces/{workspace_id}/conversations", headers=auth_headers
    ).json()
    conv_updated = next(c for c in updated if c["id"] == conv["id"])
    assert conv_updated["title"] is not None
