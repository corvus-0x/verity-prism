"""Tests for schema review endpoints: create extraction, get schema by id."""
import uuid

import pytest

from app.models.document import Document
from app.models.document_schema import DocumentSchema
from app.models.user import User


@pytest.fixture
def ws_schema_doc(db, auth_headers, client):
    user = db.query(User).filter(User.email == "analyst@example.com").first()
    assert user is not None, "registered_user fixture must run before ws_schema_doc"
    ws_resp = client.post("/workspaces/", json={"name": "Review WS", "vertical": "general"},
                          headers=auth_headers)
    ws_id = ws_resp.json()["id"]

    schema = DocumentSchema(
        id=str(uuid.uuid4()), document_type="DEED", display_name="Deed",
        vertical="general",
        schema_fields=[{"name": "grantor_name", "type": "name",
                        "description": "Grantor", "group": "Parties"}],
        version=1, is_active=True, parse_strategy="claude",
        default_confidence_threshold=0.75,
    )
    db.add(schema)
    db.flush()

    doc = Document(
        id=str(uuid.uuid4()), workspace_id=ws_id,
        filename="deed.pdf", original_filename="deed.pdf",
        file_path="/tmp/deed.pdf", file_type="pdf",
        sha256_hash="test123", uploaded_by=user.id,
        extraction_status="needs_review", schema_id=schema.id,
    )
    db.add(doc)
    db.commit()
    return ws_id, schema, doc


def test_create_extraction_inserts_attempt3_row(client, auth_headers, ws_schema_doc):
    ws_id, schema, doc = ws_schema_doc
    resp = client.post(
        f"/workspaces/{ws_id}/documents/{doc.id}/extractions",
        json={
            "field_name": "grantor_name",
            "field_value": "Jane Smith",
            "field_type": "name",
            "schema_id": schema.id,
        },
        headers=auth_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["field_name"] == "grantor_name"
    assert data["field_value"] == "Jane Smith"
    assert data["attempt"] == 3
    assert data["confidence"] == 1.0


def test_create_extraction_with_evidence(client, auth_headers, ws_schema_doc):
    ws_id, schema, doc = ws_schema_doc
    evidence = {
        "type": "manual_draw",
        "page": 1,
        "region": {"x": 100, "y": 200, "width": 150, "height": 25},
        "image_b64": "data:image/png;base64,abc123",
        "note": "First paragraph",
    }
    resp = client.post(
        f"/workspaces/{ws_id}/documents/{doc.id}/extractions",
        json={"field_name": "grantor_name", "field_value": "Jane Smith",
              "field_type": "name", "schema_id": schema.id, "evidence": evidence},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    assert resp.json()["evidence"]["type"] == "manual_draw"


def test_create_extraction_404_for_unknown_doc(client, auth_headers, ws_schema_doc):
    ws_id, schema, _ = ws_schema_doc
    resp = client.post(
        f"/workspaces/{ws_id}/documents/nonexistent/extractions",
        json={"field_name": "x", "field_value": "y", "field_type": "text",
              "schema_id": schema.id},
        headers=auth_headers,
    )
    assert resp.status_code == 404


def test_get_schema_by_id(client, auth_headers, ws_schema_doc):
    _, schema, _ = ws_schema_doc
    resp = client.get(f"/schemas/{schema.id}", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == schema.id
    assert data["document_type"] == "DEED"
    assert len(data["fields"]) == 1


def test_get_schema_by_id_404(client, auth_headers):
    resp = client.get("/schemas/nonexistent-id", headers=auth_headers)
    assert resp.status_code == 404


def test_create_extraction_flips_doc_to_complete_when_all_fields_resolved(client, auth_headers, ws_schema_doc, db):
    """When the only remaining field gets a manual extraction, doc status flips to complete."""
    ws_id, schema, doc = ws_schema_doc
    # doc starts as needs_review with no extraction rows (no low-confidence fields to fail the check)
    resp = client.post(
        f"/workspaces/{ws_id}/documents/{doc.id}/extractions",
        json={
            "field_name": "grantor_name",
            "field_value": "Jane Smith",
            "field_type": "name",
            "schema_id": schema.id,
        },
        headers=auth_headers,
    )
    assert resp.status_code == 201
    # Refresh the doc and check status
    db.expire_all()
    updated_doc = db.query(Document).filter(Document.id == doc.id).first()
    assert updated_doc.extraction_status == "complete"
