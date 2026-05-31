"""Observability dashboard endpoint tests."""
import uuid
import pytest
from app.models.document import Document
from app.models.document_schema import DocumentSchema
from app.models.user import User
from app.models.workspace import Workspace


@pytest.fixture
def ws_and_docs(db, auth_headers, client):
    """Seed one workspace with 3 docs: 1 complete, 1 needs_review, 1 failed."""
    user = db.query(User).filter(User.email == "tyler@example.com").first()
    ws = Workspace(
        id=str(uuid.uuid4()), name="Obs WS", vertical="general", created_by=user.id
    )
    db.add(ws)
    schema = DocumentSchema(
        id=str(uuid.uuid4()), document_type="DEED", display_name="Deed",
        vertical="general", schema_fields=[], version=1, is_active=True,
        parse_strategy="claude", default_confidence_threshold=0.75,
    )
    db.add(schema)
    db.flush()

    for status in ("complete", "needs_review", "failed"):
        doc = Document(
            id=str(uuid.uuid4()), workspace_id=ws.id,
            filename=f"{status}.pdf", original_filename=f"{status}.pdf",
            file_path=f"/tmp/{status}.pdf", file_type="pdf",
            sha256_hash=f"hash_{status}", uploaded_by=user.id,
            extraction_status=status, schema_id=schema.id,
        )
        db.add(doc)
    db.commit()
    return ws, schema


def test_automation_rate_returns_counts(client, auth_headers, ws_and_docs):
    resp = client.get("/observability/automation-rate", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "total" in data
    assert "automated" in data
    assert "needs_review" in data
    assert "failed" in data
    assert "automation_rate" in data
    assert data["total"] >= 3


def test_volume_returns_daily_series(client, auth_headers, ws_and_docs):
    resp = client.get("/observability/volume?days=7", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "days" in data
    assert isinstance(data["days"], list)
    assert len(data["days"]) == 7
    assert "date" in data["days"][0]
    assert "inbound" in data["days"][0]
    assert "completed" in data["days"][0]


def test_classification_details_returns_schema_rows(client, auth_headers, ws_and_docs):
    resp = client.get("/observability/classification-details", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "schemas" in data
    assert isinstance(data["schemas"], list)


def test_current_processing_returns_counts(client, auth_headers, ws_and_docs):
    resp = client.get("/observability/current-processing", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "pending" in data
    assert "needs_review" in data
    assert "total_active" in data


def test_automation_rate_excludes_other_users_workspaces(db, client, auth_headers, ws_and_docs):
    """Documents in a workspace owned by another user must not appear in the caller's metrics."""
    user = db.query(User).filter(User.email == "tyler@example.com").first()
    _, schema = ws_and_docs

    # Baseline: caller's 3 docs are visible
    resp = client.get("/observability/automation-rate", headers=auth_headers)
    baseline_total = resp.json()["total"]
    assert baseline_total >= 3

    # Create a different user and their workspace with 2 docs
    other_user = User(
        id=str(uuid.uuid4()),
        email=f"other_{uuid.uuid4()}@test.com",
        full_name="Other User",
        password_hash="x",
    )
    db.add(other_user)
    other_ws = Workspace(
        id=str(uuid.uuid4()), name="Other WS", vertical="general",
        created_by=other_user.id,
    )
    db.add(other_ws)
    db.flush()
    for i in range(2):
        db.add(Document(
            id=str(uuid.uuid4()), workspace_id=other_ws.id,
            filename=f"other_{i}.pdf", original_filename=f"other_{i}.pdf",
            file_path=f"/tmp/other_{i}.pdf", file_type="pdf",
            sha256_hash=f"other_hash_{i}", uploaded_by=other_user.id,
            extraction_status="complete", schema_id=schema.id,
        ))
    db.commit()

    # Caller's total must not have increased
    resp = client.get("/observability/automation-rate", headers=auth_headers)
    assert resp.json()["total"] == baseline_total, (
        "Other user's documents leaked into automation-rate response"
    )
