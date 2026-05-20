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
    content = b"%PDF-1.4 Grantor: Karen Homan. Grantee: Do Good Real Estate LLC."

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
