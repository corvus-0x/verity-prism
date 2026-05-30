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
