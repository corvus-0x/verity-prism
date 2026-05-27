import io
import pytest
from unittest.mock import patch, MagicMock


@pytest.fixture
def workspace_id(client, auth_headers):
    return client.post("/workspaces/", json={"name": "Test"},
                       headers=auth_headers).json()["id"]


def test_extractions_created_after_upload(client, auth_headers, workspace_id):
    """
    Upload a document with Claude mocked. The pipeline runs synchronously
    in tests (BackgroundTasks execute inline with TestClient), so we can
    immediately check for extraction rows.
    """
    content = b"%PDF-1.4 Grantor: Jane Smith. Grantee: Acme Real Estate LLC."

    with patch("app.services.extraction_engine.Anthropic") as mock_anthropic:
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client
        mock_client.messages.create.return_value = MagicMock(
            content=[MagicMock(text='{"document_type": "DEED"}')]
        )

        response = client.post(
            f"/workspaces/{workspace_id}/documents",
            files={"file": ("deed.pdf", io.BytesIO(content), "application/pdf")},
            headers=auth_headers,
        )

    assert response.status_code == 201
    doc_id = response.json()["id"]

    extractions = client.get(
        f"/workspaces/{workspace_id}/documents/{doc_id}/extractions",
        headers=auth_headers,
    )
    assert extractions.status_code == 200
    assert isinstance(extractions.json(), list)


def test_no_schema_document_returns_pending(client, auth_headers, workspace_id):
    """
    When a document is uploaded, the endpoint returns immediately with
    extraction_status='pending'. The background task handles no_schema
    detection and lead creation — verified in integration tests, not here.
    """
    content = b"Some unknown document type content here."

    with patch("app.services.extraction_engine.Anthropic") as mock_anthropic:
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client
        mock_client.messages.create.return_value = MagicMock(
            content=[MagicMock(text='{"document_type": "COURT-FILING"}')]
        )

        response = client.post(
            f"/workspaces/{workspace_id}/documents",
            files={"file": ("court.pdf", io.BytesIO(content), "application/pdf")},
            headers=auth_headers,
        )

    assert response.status_code == 201
    doc = response.json()
    # Upload always returns pending immediately — pipeline runs in background
    assert doc["extraction_status"] == "pending"
    assert doc["original_filename"] == "court.pdf"
    assert len(doc["sha256_hash"]) == 64


from app.services.xml_parser import is_valid_xml_bytes


def test_is_valid_xml_bytes_returns_true_for_valid_xml():
    xml = b"<?xml version='1.0'?><root><child>value</child></root>"
    assert is_valid_xml_bytes(xml) is True


def test_is_valid_xml_bytes_returns_false_for_non_xml():
    assert is_valid_xml_bytes(b"%PDF-1.4 not xml") is False
    assert is_valid_xml_bytes(b"") is False
    assert is_valid_xml_bytes(b"just some text") is False


import uuid
from unittest.mock import patch, MagicMock
from app.models.document_schema import DocumentSchema
from app.models.workspace import Workspace
from app.models.user import User
from app.models.document import Document


def test_pipeline_uses_xml_parser_when_parse_strategy_is_xml_direct(db):
    """When schema.parse_strategy == 'xml_direct', pipeline calls parse_xml_document, not extract_fields."""
    user = User(
        id=str(uuid.uuid4()),
        email=f"ptest_{uuid.uuid4()}@test.com",
        full_name="Pipeline Test",
        password_hash="x",
    )
    db.add(user)
    ws = Workspace(
        id=str(uuid.uuid4()),
        name="Pipeline WS",
        vertical="general",
        created_by=user.id,
    )
    db.add(ws)
    schema = DocumentSchema(
        id=str(uuid.uuid4()),
        document_type="TEST-XML-TYPE",
        display_name="Test XML Type",
        vertical="general",
        schema_fields=[{"name": "test_field", "type": "text", "description": "TestElement — test field"}],
        extraction_prompt="Extract fields.",
        version=1,
        is_active=True,
        parse_strategy="xml_direct",
        default_confidence_threshold=1.0,
    )
    db.add(schema)
    db.flush()
    doc = Document(
        id=str(uuid.uuid4()),
        workspace_id=ws.id,
        filename="test.xml",
        original_filename="test.xml",
        file_path="/tmp/test.xml",
        file_type="xml",
        sha256_hash="abc123",
        uploaded_by=user.id,
    )
    db.add(doc)
    db.commit()

    valid_xml = b"<?xml version='1.0'?><root><TestElement>hello</TestElement></root>"

    with patch("app.services.document_pipeline.detect_document_type", return_value="TEST-XML-TYPE"), \
         patch("app.services.document_pipeline.extract_text", return_value="test content"), \
         patch("app.services.document_pipeline.generate_standardized_name", return_value="test.xml"), \
         patch("app.services.document_pipeline.extract_fields") as mock_claude, \
         patch("app.services.document_pipeline.parse_xml_document", return_value=[]) as mock_xml:

        from app.services.document_pipeline import _run_pipeline
        _run_pipeline(doc.id, valid_xml, "test.xml", ws.id, user.id, db)

    mock_xml.assert_called_once()
    mock_claude.assert_not_called()


def test_pipeline_uses_claude_when_parse_strategy_is_claude(db):
    """When schema.parse_strategy == 'claude', pipeline calls extract_fields, not parse_xml_document."""
    user = User(
        id=str(uuid.uuid4()),
        email=f"ptest2_{uuid.uuid4()}@test.com",
        full_name="Pipeline Test 2",
        password_hash="x",
    )
    db.add(user)
    ws = Workspace(
        id=str(uuid.uuid4()),
        name="Pipeline WS 2",
        vertical="general",
        created_by=user.id,
    )
    db.add(ws)
    schema = DocumentSchema(
        id=str(uuid.uuid4()),
        document_type="TEST-CLAUDE-TYPE",
        display_name="Test Claude Type",
        vertical="general",
        schema_fields=[],
        extraction_prompt="Extract fields.",
        version=1,
        is_active=True,
        parse_strategy="claude",
        default_confidence_threshold=0.75,
    )
    db.add(schema)
    db.flush()
    doc = Document(
        id=str(uuid.uuid4()),
        workspace_id=ws.id,
        filename="test.pdf",
        original_filename="test.pdf",
        file_path="/tmp/test.pdf",
        file_type="pdf",
        sha256_hash="def456",
        uploaded_by=user.id,
    )
    db.add(doc)
    db.commit()

    with patch("app.services.document_pipeline.detect_document_type", return_value="TEST-CLAUDE-TYPE"), \
         patch("app.services.document_pipeline.extract_text", return_value="deed content"), \
         patch("app.services.document_pipeline.generate_standardized_name", return_value="test.pdf"), \
         patch("app.services.document_pipeline.extract_fields", return_value=[]) as mock_claude, \
         patch("app.services.document_pipeline.parse_xml_document") as mock_xml:

        from app.services.document_pipeline import _run_pipeline
        _run_pipeline(doc.id, b"%PDF test", "test.pdf", ws.id, user.id, db)

    mock_claude.assert_called_once()
    mock_xml.assert_not_called()
