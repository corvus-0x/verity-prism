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

    mock_client = MagicMock()
    mock_client.messages.create.return_value = _mock_end_turn(
        "Based on the workspace data, I found relevant records."
    )
    with patch("app.services.claude_client.get_client", return_value=mock_client):
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

    mock_client = MagicMock()
    mock_client.messages.create.return_value = _mock_end_turn("Here is what I found.")
    with patch("app.services.claude_client.get_client", return_value=mock_client):
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


def test_multi_turn_conversation_no_duplicate_user_message(client, auth_headers, workspace_id):
    conv = client.post(
        f"/workspaces/{workspace_id}/conversations", headers=auth_headers
    ).json()

    mock_client = MagicMock()
    mock_client.messages.create.return_value = _mock_end_turn("First answer.")
    with patch("app.services.claude_client.get_client", return_value=mock_client):
        client.post(
            f"/workspaces/{workspace_id}/conversations/{conv['id']}/messages",
            json={"content": "First question"},
            headers=auth_headers,
        )

    mock_client = MagicMock()
    mock_client.messages.create.return_value = _mock_end_turn("Second answer.")
    with patch("app.services.claude_client.get_client", return_value=mock_client):
        response = client.post(
            f"/workspaces/{workspace_id}/conversations/{conv['id']}/messages",
            json={"content": "Second question"},
            headers=auth_headers,
        )

    assert response.status_code == 201
    assert response.json()["content"] == "Second answer."

    # Verify the messages list sent to Claude on the second call has no duplicate user turns
    mock_client = MagicMock()
    mock_client.messages.create.return_value = _mock_end_turn("Third answer.")
    with patch("app.services.claude_client.get_client", return_value=mock_client):
        client.post(
            f"/workspaces/{workspace_id}/conversations/{conv['id']}/messages",
            json={"content": "Third question"},
            headers=auth_headers,
        )
        # The messages sent to Claude should alternate user/assistant properly
        call_args = mock_client.messages.create.call_args
        messages_sent = call_args[1]["messages"]
        roles = [m["role"] for m in messages_sent]
        # Should alternate: user, assistant, user, assistant, user — no consecutive duplicates
        for i in range(len(roles) - 1):
            assert roles[i] != roles[i + 1], f"Duplicate consecutive role at index {i}: {roles}"


# ---------------------------------------------------------------------------
# Agentic loop mechanic tests
# ---------------------------------------------------------------------------
from app.services.ai_engine import chat, _synthesis_pass, _extract_text
from app.models.workspace import Workspace
from app.models.ai import AIConversation
import uuid


@pytest.fixture
def ws_and_conv(db):
    from app.models.user import User
    import hashlib
    user = User(
        id=str(uuid.uuid4()),
        email="loop_test@example.com",
        password_hash=hashlib.sha256(b"password").hexdigest(),
        full_name="Loop Test User",
    )
    db.add(user)
    db.commit()
    ws = Workspace(id=str(uuid.uuid4()), name="Loop Test WS", vertical="fraud", created_by=user.id)
    db.add(ws)
    db.flush()  # Ensure ws.id is visible within this transaction before conv FK check
    conv = AIConversation(id=str(uuid.uuid4()), workspace_id=ws.id, user_id=user.id)
    db.add(conv)
    db.commit()
    return ws, conv


def _mock_tool_use_then_end_turn(tool_name: str, tool_input: dict, final_text: str):
    """Return two side_effect responses: round 1 = tool_use, round 2 = end_turn."""
    # Round 1: Claude requests a tool call
    tool_block = MagicMock()
    tool_block.type = "tool_use"
    tool_block.id = "tool_abc123"
    tool_block.name = tool_name
    tool_block.input = tool_input

    round1 = MagicMock()
    round1.stop_reason = "tool_use"
    round1.content = [tool_block]

    # Round 2: Claude returns a final text answer
    text_block = MagicMock()
    text_block.type = "text"
    text_block.text = final_text

    round2 = MagicMock()
    round2.stop_reason = "end_turn"
    round2.content = [text_block]

    return [round1, round2]


def test_chat_executes_tool_and_returns_final_answer(db, ws_and_conv):
    ws, conv = ws_and_conv
    side_effects = _mock_tool_use_then_end_turn(
        tool_name="get_findings",
        tool_input={},
        final_text="No findings recorded yet in this workspace.",
    )
    mock_client = MagicMock()
    mock_client.messages.create.side_effect = side_effects
    with patch("app.services.claude_client.get_client", return_value=mock_client):
        result = chat(ws.id, conv.id, "What findings exist?", db)

    assert result == "No findings recorded yet in this workspace."
    assert mock_client.messages.create.call_count == 2


def test_chat_synthesis_pass_triggered_at_max_rounds(db, ws_and_conv):
    ws, conv = ws_and_conv

    # 10 tool_use rounds then 1 synthesis end_turn
    tool_block = MagicMock()
    tool_block.type = "tool_use"
    tool_block.id = "tool_xyz"
    tool_block.name = "get_findings"
    tool_block.input = {}

    tool_round = MagicMock()
    tool_round.stop_reason = "tool_use"
    tool_round.content = [tool_block]

    synthesis_text = MagicMock()
    synthesis_text.type = "text"
    synthesis_text.text = "Synthesized answer after max rounds."

    synthesis_round = MagicMock()
    synthesis_round.stop_reason = "end_turn"
    synthesis_round.content = [synthesis_text]

    side_effects = [tool_round] * 10 + [synthesis_round]

    mock_client = MagicMock()
    mock_client.messages.create.side_effect = side_effects
    with patch("app.services.claude_client.get_client", return_value=mock_client):
        result = chat(ws.id, conv.id, "Run a deep analysis.", db)

    assert result == "Synthesized answer after max rounds."
    # 10 tool rounds + 1 synthesis call
    assert mock_client.messages.create.call_count == 11


def test_extract_text_returns_first_text_block():
    block = MagicMock()
    block.text = "Hello from Claude"
    response = MagicMock()
    response.content = [block]
    assert _extract_text(response) == "Hello from Claude"


def test_extract_text_fallback_when_no_text_block():
    block = MagicMock(spec=[])  # no 'text' attribute
    response = MagicMock()
    response.content = [block]
    assert _extract_text(response) == "I was unable to produce a response."


def test_get_conversation_history_workspace_scoped(db):
    """L1: history lookup must filter by workspace_id, not conversation_id alone."""
    import uuid, hashlib
    from app.models.user import User
    from app.models.workspace import Workspace
    from app.models.ai import AIConversation, AIMessage
    from app.services.ai_engine import get_conversation_history

    user = User(id=str(uuid.uuid4()), email=f"l1_{uuid.uuid4().hex[:6]}@test.com",
                password_hash=hashlib.sha256(b"x").hexdigest(), full_name="L1 User")
    db.add(user)
    db.commit()

    ws1 = Workspace(id=str(uuid.uuid4()), name="WS1", vertical="fraud", created_by=user.id)
    ws2 = Workspace(id=str(uuid.uuid4()), name="WS2", vertical="fraud", created_by=user.id)
    db.add_all([ws1, ws2])
    db.commit()

    conv = AIConversation(id=str(uuid.uuid4()), workspace_id=ws1.id, user_id=user.id)
    db.add(conv)
    db.commit()

    msg = AIMessage(id=str(uuid.uuid4()), conversation_id=conv.id, role="user", content="secret message")
    db.add(msg)
    db.commit()

    # Correct workspace — should return the message
    history = get_conversation_history(conv.id, ws1.id, db)
    assert len(history) == 1
    assert history[0]["content"] == "secret message"

    # Wrong workspace — must return nothing even though conversation_id matches
    history_wrong_ws = get_conversation_history(conv.id, ws2.id, db)
    assert history_wrong_ws == []


def test_chat_uses_chat_model(db, ws_and_conv):
    """The chat path routes Claude calls through the shared CHAT_MODEL constant."""
    from app.services.claude_client import CHAT_MODEL

    ws, conv = ws_and_conv
    mock_client = MagicMock()
    mock_client.messages.create.return_value = _mock_end_turn("answer")
    with patch("app.services.claude_client.get_client", return_value=mock_client):
        chat(ws.id, conv.id, "hi", db)

    _, kwargs = mock_client.messages.create.call_args
    assert kwargs["model"] == CHAT_MODEL
