"""Review router tests — flag endpoint."""

import uuid

import pytest

from app.models.document import Document
from app.models.document_extraction import DocumentExtraction
from app.models.document_schema import DocumentSchema
from app.models.user import User


@pytest.fixture
def workspace_id(client, auth_headers):
    return client.post(
        "/workspaces/", json={"name": "Review Test", "vertical": "general"}, headers=auth_headers
    ).json()["id"]


@pytest.fixture
def document_with_review_status(db, workspace_id, auth_headers):
    """A document already in needs_review state."""
    user = db.query(User).filter(User.email == "analyst@example.com").first()
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


@pytest.fixture
def low_conf_extraction(db, document_with_review_status):
    """A latest extraction below threshold (attempt 1, confidence 0.5) on the
    needs_review document — the row a human correction targets."""
    doc = document_with_review_status
    row = DocumentExtraction(
        id=str(uuid.uuid4()),
        document_id=doc.id,
        workspace_id=doc.workspace_id,
        field_name="grantor_name",
        field_value="J. Smth",
        field_type="name",
        confidence=0.5,
        ocr_confidence=0.9,
        schema_id=doc.schema_id,
        attempt=1,
    )
    db.add(row)
    db.commit()
    return doc, row


def test_correct_extraction_inserts_attempt3_correction(
    client, auth_headers, workspace_id, low_conf_extraction
):
    doc, row = low_conf_extraction
    resp = client.patch(
        f"/workspaces/{workspace_id}/documents/{doc.id}/extractions/{row.id}/correct",
        json={"field_value": "Jane Smith"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["field_value"] == "Jane Smith"
    assert data["attempt"] == 3
    assert data["confidence"] == 1.0


def test_correct_extraction_rejected_for_wrong_workspace(client, auth_headers, low_conf_extraction):
    doc, row = low_conf_extraction
    other_ws = client.post(
        "/workspaces/", json={"name": "Other", "vertical": "general"}, headers=auth_headers
    ).json()["id"]
    resp = client.patch(
        f"/workspaces/{other_ws}/documents/{doc.id}/extractions/{row.id}/correct",
        json={"field_value": "X"},
        headers=auth_headers,
    )
    assert resp.status_code == 404


def test_correct_extraction_large_evidence_returns_413(
    client, auth_headers, workspace_id, low_conf_extraction
):
    doc, row = low_conf_extraction
    resp = client.patch(
        f"/workspaces/{workspace_id}/documents/{doc.id}/extractions/{row.id}/correct",
        json={"field_value": "Jane", "evidence": {"blob": "x" * 210_000}},
        headers=auth_headers,
    )
    assert resp.status_code == 413


def test_get_review_queue_lists_needs_review_doc(
    client, auth_headers, workspace_id, low_conf_extraction
):
    doc, _ = low_conf_extraction
    resp = client.get(f"/workspaces/{workspace_id}/review-queue", headers=auth_headers)
    assert resp.status_code == 200
    item = next((i for i in resp.json() if i["document_id"] == doc.id), None)
    assert item is not None
    assert item["low_confidence_count"] >= 1


def test_flag_document_stores_reason_and_note(
    client, auth_headers, workspace_id, document_with_review_status
):
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


def test_flag_document_with_no_note(
    client, auth_headers, workspace_id, document_with_review_status
):
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


def test_flag_document_rejected_for_wrong_workspace(
    client, auth_headers, document_with_review_status
):
    """Cannot flag a document belonging to a different workspace."""
    doc = document_with_review_status
    # Create a second workspace
    other_ws = client.post(
        "/workspaces/", json={"name": "Other WS", "vertical": "general"}, headers=auth_headers
    ).json()["id"]
    resp = client.patch(
        f"/workspaces/{other_ws}/documents/{doc.id}/flag",
        json={"flag_reason": "other"},
        headers=auth_headers,
    )
    # Document doesn't belong to other_ws — should 404
    assert resp.status_code == 404
