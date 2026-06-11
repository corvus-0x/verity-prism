"""
Extraction engine unit tests — _extract_batch behavior that doesn't need a DB.
Claude calls are mocked via patch("app.services.claude_client.get_client").
"""

from unittest.mock import MagicMock, patch

from app.models.document_schema import DocumentSchema
from app.services import extraction_engine


def _mock_response(text: str = '{"extractions": []}'):
    resp = MagicMock()
    block = MagicMock()
    block.text = text
    resp.content = [block]
    resp.usage = MagicMock(input_tokens=10, output_tokens=5)
    return resp


def _schema():
    s = DocumentSchema(
        document_type="TEST",
        schema_fields=[{"name": "ein", "type": "string", "description": "EIN number"}],
    )
    s.id = "schema-1"
    return s


def test_extract_batch_max_tokens_scales_to_full_batch():
    """A full 40-field batch needs ~4200 output tokens (40 × 100 + 200).

    Regression: the cap was 4096, which silently clamped full batches and
    could truncate the JSON mid-response — the same failure mode the
    2026-05-20 demo hardening fixed once already at max_tokens=2000.
    """
    fields = [
        {"name": f"field_{i}", "type": "string", "description": f"Field {i}"} for i in range(40)
    ]
    mock_client = MagicMock()
    mock_client.messages.create.return_value = _mock_response()

    with patch("app.services.claude_client.get_client", return_value=mock_client):
        extraction_engine._extract_batch(
            "document text",
            fields,
            _schema(),
            document_id=None,
            workspace_id=None,
            call_type="extraction_batch",
            attempt=1,
        )

    _, kwargs = mock_client.messages.create.call_args
    assert kwargs["max_tokens"] == 40 * 100 + 200


def test_extract_batch_preserves_empty_string_field_value():
    """An explicitly-empty extracted value ('') must survive normalisation.

    Regression: `item.get("field_value") or item.get("value")` treated ''
    as missing and coerced it to None, erasing the distinction between
    'extracted as empty' and 'key absent from response'.
    """
    response_text = (
        '{"extractions": [{"field_name": "ein", "field_value": "", '
        '"field_type": "text", "confidence": 0.9, "ocr_confidence": 0.9}]}'
    )
    mock_client = MagicMock()
    mock_client.messages.create.return_value = _mock_response(response_text)

    with patch("app.services.claude_client.get_client", return_value=mock_client):
        result = extraction_engine._extract_batch(
            "document text",
            [{"name": "ein", "type": "string", "description": "EIN number"}],
            _schema(),
            document_id=None,
            workspace_id=None,
            call_type="extraction_batch",
            attempt=1,
        )

    assert len(result) == 1
    assert result[0]["field_value"] == ""
