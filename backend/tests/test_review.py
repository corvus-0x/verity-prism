"""Review router tests — flag endpoint."""
import uuid
import pytest
from app.models.document import Document
from app.models.document_schema import DocumentSchema
from app.models.user import User
from app.models.workspace import Workspace


@pytest.fixture
def workspace_id(client, auth_headers):
    return client.post("/workspaces/", json={"name": "Review Test", "vertical": "general"},
                       headers=auth_headers).json()["id"]


@pytest.fixture
def document_with_review_status(db, workspace_id, auth_headers):
    """A document already in needs_review state."""
    user = db.query(User).filter(User.email == "tyler@example.com").first()
    schema = DocumentSchema(
        id=str(uuid.uuid4()),
        document_type="DEED",
        display_name="Deed",
        vertical="general",
        schema_fields=[],
        version=1,
        is_active=True,
        parse_strategy="claude",
        default_confidence_threshold=0.75,
    )
    db.add(schema)
    db.flush()
    doc = Document(
        id=str(uuid.uuid4()),
        workspace_id=workspace_id,
        filename="test.pdf",
        original_filename="test.pdf",
        file_path="/tmp/test.pdf",
        file_type="pdf",
        sha256_hash="flag123",
        uploaded_by=user.id,
        extraction_status="needs_review",
        schema_id=schema.id,
    )
    db.add(doc)
    db.commit()
    return doc


def test_flag_document_stores_reason_and_note(client, auth_headers, workspace_id, document_with_review_status):
    doc = document_with_review_status
    resp = client.patch(
        f"/workspaces/{workspace_id}/documents/{doc.id}/flag",
        json={"flag_reason": "low_quality_scan", "flag_note": "Pages 3-5 unreadable"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["flag_reason"] == "low_quality_scan"
    assert data["flag_note"] == "Pages 3-5 unreadable"


def test_flag_document_with_no_note(client, auth_headers, workspace_id, document_with_review_status):
    doc = document_with_review_status
    resp = client.patch(
        f"/workspaces/{workspace_id}/documents/{doc.id}/flag",
        json={"flag_reason": "unknown_type"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["flag_reason"] == "unknown_type"
    assert resp.json()["flag_note"] is None


def test_flag_document_returns_404_for_unknown_doc(client, auth_headers, workspace_id):
    resp = client.patch(
        f"/workspaces/{workspace_id}/documents/nonexistent-id/flag",
        json={"flag_reason": "other"},
        headers=auth_headers,
    )
    assert resp.status_code == 404
