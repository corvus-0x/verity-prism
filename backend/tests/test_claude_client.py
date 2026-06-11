from unittest.mock import MagicMock, patch


def test_get_client_returns_same_instance_on_repeated_calls():
    """get_client() is a lazy singleton — same object every time."""
    # Reset the singleton between test runs
    import app.services.claude_client as cc

    cc._client = None

    from app.services.claude_client import get_client

    c1 = get_client()
    c2 = get_client()
    assert c1 is c2

    # Cleanup
    cc._client = None


def test_patching_get_client_intercepts_services(db):
    """Patching claude_client.get_client intercepts calls in services that use it."""
    mock_client = MagicMock()
    mock_client.messages.create.return_value = MagicMock(
        content=[MagicMock(text='{"document_type": "DEED"}')]
    )
    with patch("app.services.claude_client.get_client", return_value=mock_client):
        from app.services.extraction_engine import detect_document_type

        detect_document_type("Grantor: John Smith", db)

    mock_client.messages.create.assert_called_once()


def test_model_constants_are_distinct():
    from app.services import claude_client

    # Extraction uses the cheaper model; chat uses the stronger one.
    assert claude_client.EXTRACTION_MODEL == "claude-haiku-4-5-20251001"
    assert claude_client.CHAT_MODEL == "claude-sonnet-4-6"
    assert claude_client.EXTRACTION_MODEL != claude_client.CHAT_MODEL


def test_get_client_without_langsmith_key_returns_plain_client(monkeypatch):
    """When langsmith_api_key is unset, client is a plain Anthropic instance."""
    from app.config import settings

    monkeypatch.setattr(settings, "langsmith_api_key", None)
    import app.services.claude_client as cc

    cc._client = None
    client = cc.get_client()
    from anthropic import Anthropic

    assert isinstance(client, Anthropic)
    cc._client = None  # clean up singleton


def test_get_client_wraps_with_langsmith_when_key_set(monkeypatch):
    """When langsmith_api_key is set, wrap_anthropic is called."""
    from app.config import settings

    monkeypatch.setattr(settings, "langsmith_api_key", "ls__test_key")

    import app.services.claude_client as cc

    cc._client = None
    mock_wrapped = MagicMock()
    with patch("langsmith.wrappers.wrap_anthropic", return_value=mock_wrapped) as mock_wrap:
        client = cc.get_client()
        mock_wrap.assert_called_once()
        assert client is mock_wrapped
    cc._client = None  # clean up singleton
