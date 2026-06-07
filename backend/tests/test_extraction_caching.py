from unittest.mock import MagicMock, patch

from app.models.document_schema import DocumentSchema
from app.services import extraction_engine
from app.services.claude_client import EXTRACTION_MODEL


def _mock_response():
    """Minimal Anthropic-style response. _extract_batch parses
    json.loads(strip_json_fences(content[0].text)).get('extractions', [])."""
    resp = MagicMock()
    block = MagicMock()
    block.text = '{"extractions": []}'
    resp.content = [block]
    resp.usage = MagicMock(
        input_tokens=10, output_tokens=5,
        cache_creation_input_tokens=0, cache_read_input_tokens=0,
    )
    return resp


def _schema():
    s = DocumentSchema(document_type="TEST", schema_fields=[
        {"name": "ein", "type": "string", "description": "EIN number"}
    ])
    s.id = "schema-1"
    return s


def test_extract_batch_uses_extraction_model():
    mock_client = MagicMock()
    mock_client.messages.create.return_value = _mock_response()

    with patch("app.services.claude_client.get_client", return_value=mock_client):
        extraction_engine._extract_batch(
            "some document text",
            [{"name": "ein", "type": "string", "description": "EIN number"}],
            _schema(),
            document_id=None, workspace_id=None,
            call_type="extraction_batch", attempt=1,
        )

    _, kwargs = mock_client.messages.create.call_args
    assert kwargs["model"] == EXTRACTION_MODEL


def test_extract_batch_marks_static_block_as_cacheable():
    mock_client = MagicMock()
    mock_client.messages.create.return_value = _mock_response()

    with patch("app.services.claude_client.get_client", return_value=mock_client):
        extraction_engine._extract_batch(
            "document body text here",
            [{"name": "ein", "type": "string", "description": "EIN number"}],
            _schema(),
            document_id=None, workspace_id=None,
            call_type="extraction_batch", attempt=1,
        )

    _, kwargs = mock_client.messages.create.call_args
    content = kwargs["messages"][0]["content"]

    assert isinstance(content, list)  # blocks, not a bare string

    cached = [b for b in content if b.get("cache_control")]
    assert len(cached) == 1
    assert cached[0]["cache_control"] == {"type": "ephemeral"}

    # Static block holds field instructions; document text is a later, uncached block.
    cached_index = content.index(cached[0])
    doc_block = next(b for b in content if "document body text here" in b.get("text", ""))
    assert content.index(doc_block) > cached_index
    assert "cache_control" not in doc_block


def test_extract_batch_logging_tolerates_cache_usage_fields():
    mock_client = MagicMock()
    resp = _mock_response()
    resp.usage.cache_creation_input_tokens = 120
    resp.usage.cache_read_input_tokens = 0
    mock_client.messages.create.return_value = resp

    with patch("app.services.claude_client.get_client", return_value=mock_client):
        result = extraction_engine._extract_batch(
            "text",
            [{"name": "ein", "type": "string", "description": "EIN"}],
            _schema(),
            document_id=None, workspace_id=None,
            call_type="extraction_batch", attempt=1,
        )
    assert result == []
