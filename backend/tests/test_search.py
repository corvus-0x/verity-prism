import uuid
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import text

from app.models.document import Document
from app.models.user import User
from app.models.workspace import Workspace
from app.services.search_service import run_search


@pytest.fixture
def workspace_id(client, auth_headers):
    return client.post("/workspaces/", json={"name": "Test"}, headers=auth_headers).json()["id"]


# ── Service-level fixtures for direct run_search tests ──────────────────────


@pytest.fixture
def user(db):
    u = User(
        id=str(uuid.uuid4()),
        email=f"search_{uuid.uuid4().hex[:8]}@example.com",
        password_hash="hashed",
        full_name="Search Test User",
    )
    db.add(u)
    db.commit()
    return u


@pytest.fixture
def workspace(db, user):
    ws = Workspace(id=str(uuid.uuid4()), name="Search WS", vertical="fraud", created_by=user.id)
    db.add(ws)
    db.commit()
    return ws


def _make_doc(db, workspace, user, content: str, is_deleted: bool = False) -> Document:
    doc = Document(
        id=str(uuid.uuid4()),
        workspace_id=workspace.id,
        filename="deed.pdf",
        original_filename="deed.pdf",
        file_path="/uploads/deed.pdf",
        file_type="pdf",
        sha256_hash=uuid.uuid4().hex * 2,
        uploaded_by=user.id,
        detected_doc_type="DEED",
        is_deleted=is_deleted,
        deleted_at=datetime.now(UTC) if is_deleted else None,
    )
    db.add(doc)
    db.commit()
    db.execute(
        text("UPDATE documents SET search_vector = to_tsvector('english', :c) WHERE id = :id"),
        {"c": content, "id": doc.id},
    )
    db.commit()
    return doc


def test_search_endpoint_exists(client, auth_headers, workspace_id):
    mock_client = MagicMock()
    mock_client.messages.create.return_value = MagicMock(
        content=[
            MagicMock(text='{"fts_query": "deed", "field_filters": [], "doc_type_filter": null}')
        ]
    )
    with patch("app.services.claude_client.get_client", return_value=mock_client):
        response = client.post(
            f"/workspaces/{workspace_id}/search",
            json={"query": "find all deeds"},
            headers=auth_headers,
        )
    assert response.status_code == 200
    assert "results" in response.json()
    assert "query" in response.json()


def test_empty_workspace_returns_empty_results(client, auth_headers, workspace_id):
    mock_client = MagicMock()
    mock_client.messages.create.return_value = MagicMock(
        content=[
            MagicMock(
                text='{"fts_query": "anything", "field_filters": [], "doc_type_filter": null}'
            )
        ]
    )
    with patch("app.services.claude_client.get_client", return_value=mock_client):
        response = client.post(
            f"/workspaces/{workspace_id}/search",
            json={"query": "anything"},
            headers=auth_headers,
        )
    assert response.status_code == 200
    assert response.json()["results"] == []


def test_search_is_audit_logged(client, auth_headers, workspace_id, db):
    from app.models.audit import AuditLog

    mock_client = MagicMock()
    mock_client.messages.create.return_value = MagicMock(
        content=[
            MagicMock(text='{"fts_query": "test", "field_filters": [], "doc_type_filter": null}')
        ]
    )
    with patch("app.services.claude_client.get_client", return_value=mock_client):
        client.post(
            f"/workspaces/{workspace_id}/search",
            json={"query": "test search"},
            headers=auth_headers,
        )
    log_entry = db.query(AuditLog).filter(AuditLog.action == "searched").first()
    assert log_entry is not None


# ── H1: soft-deleted documents must not surface in search results ────────────


def test_run_search_fts_excludes_soft_deleted(db, workspace, user):
    """H1: FTS branch — soft-deleted doc must not appear even when its text matches."""
    _make_doc(db, workspace, user, "grantor john smith deed transfer", is_deleted=False)
    deleted = _make_doc(db, workspace, user, "grantor jane doe deleted deed", is_deleted=True)

    results = run_search(
        workspace.id,
        {"fts_query": "grantor jane doe deleted", "field_filters": [], "doc_type_filter": None},
        db,
    )
    ids = [r["document_id"] for r in results]
    assert deleted.id not in ids


def test_run_search_field_filter_excludes_soft_deleted(db, workspace, user):
    """H1: field-filter-only branch — soft-deleted doc must not be fetched directly."""
    from app.models.document_extraction import DocumentExtraction

    active = _make_doc(db, workspace, user, "parcel record value", is_deleted=False)
    deleted = _make_doc(db, workspace, user, "parcel record value", is_deleted=True)

    for doc in (active, deleted):
        db.add(
            DocumentExtraction(
                id=str(uuid.uuid4()),
                document_id=doc.id,
                workspace_id=workspace.id,
                field_name="grantor",
                field_value="John Smith",
                field_type="text",
                confidence=0.95,
            )
        )
    db.commit()

    results = run_search(
        workspace.id,
        {
            "fts_query": "",
            "field_filters": [{"field_name": "grantor", "operator": "eq", "value": "John Smith"}],
            "doc_type_filter": None,
        },
        db,
    )
    ids = [r["document_id"] for r in results]
    assert active.id in ids
    assert deleted.id not in ids


# ── H2: search_vector column type and GIN index ──────────────────────────────


def test_search_vector_column_is_tsvector(test_engine):
    """H2: search_vector must be TSVECTOR type, not TEXT."""
    with test_engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT data_type FROM information_schema.columns WHERE table_name = 'documents' AND column_name = 'search_vector'"
            )
        ).fetchone()
    assert row is not None
    assert row[0] == "tsvector", f"Expected tsvector but got {row[0]}"


def test_search_vector_gin_index_exists(test_engine):
    """H2: GIN index must exist on documents.search_vector for performant FTS."""
    with test_engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT indexname FROM pg_indexes WHERE tablename = 'documents' AND indexdef ILIKE '%gin%search_vector%'"
            )
        ).fetchone()
    assert row is not None, "No GIN index found on documents.search_vector"


def test_run_search_keyword_mode_returns_mode_in_response(auth_headers, client):
    """mode='keyword' is accepted and reflected in response."""
    ws_resp = client.post(
        "/workspaces/",
        json={"name": "search-mode-test", "vertical": "general"},
        headers=auth_headers,
    )
    workspace_id = ws_resp.json()["id"]

    mock_client = MagicMock()
    mock_client.messages.create.return_value = MagicMock(
        content=[
            MagicMock(
                text='{"fts_query": "property transfer", "field_filters": [], "doc_type_filter": null}'
            )
        ]
    )
    with patch("app.services.claude_client.get_client", return_value=mock_client):
        response = client.post(
            f"/workspaces/{workspace_id}/search/",
            json={"query": "property transfer", "mode": "keyword"},
            headers=auth_headers,
        )
    assert response.status_code == 200
    assert response.json()["mode"] == "keyword"


def test_run_search_default_mode_is_hybrid(auth_headers, client):
    """Omitting mode defaults to hybrid."""
    ws_resp = client.post(
        "/workspaces/",
        json={"name": "search-default-test", "vertical": "general"},
        headers=auth_headers,
    )
    workspace_id = ws_resp.json()["id"]

    mock_client = MagicMock()
    mock_client.messages.create.return_value = MagicMock(
        content=[
            MagicMock(
                text='{"fts_query": "property transfer", "field_filters": [], "doc_type_filter": null}'
            )
        ]
    )
    with patch("app.services.claude_client.get_client", return_value=mock_client):
        response = client.post(
            f"/workspaces/{workspace_id}/search/",
            json={"query": "property transfer"},
            headers=auth_headers,
        )
    assert response.status_code == 200
    assert response.json()["mode"] == "hybrid"


# ── Field-filter correctness: scan window and attempt history ────────────────


def test_run_search_field_filters_not_capped_by_fts_scan_window(db, workspace, user):
    """Field filters must intersect against ALL FTS matches, not the first 50.

    Regression: limit(50) was applied to the FTS query BEFORE intersecting
    with field-filter doc IDs, silently dropping matching documents that sat
    past the scan window in a large workspace.
    """
    from app.models.document_extraction import DocumentExtraction

    docs = [_make_doc(db, workspace, user, "shared corpus keyword") for _ in range(60)]
    early, late = docs[0], docs[-1]
    for doc in (early, late):
        db.add(
            DocumentExtraction(
                id=str(uuid.uuid4()),
                document_id=doc.id,
                workspace_id=workspace.id,
                field_name="grantor",
                field_value="John Smith",
                field_type="text",
                confidence=0.95,
            )
        )
    db.commit()

    results = run_search(
        workspace.id,
        {
            "fts_query": "shared corpus keyword",
            "field_filters": [{"field_name": "grantor", "operator": "eq", "value": "John Smith"}],
            "doc_type_filter": None,
        },
        db,
        mode="keyword",
    )
    ids = {r["document_id"] for r in results}
    assert early.id in ids
    assert late.id in ids, "doc matching all filters was dropped by the FTS scan window"


def test_run_search_matched_fields_uses_latest_attempt(db, workspace, user):
    """matched_fields must show the latest attempt per field, not whichever
    row the database happens to return last.

    Insert the human correction (attempt=3) BEFORE the stale attempt=1 row so
    an implementation that relies on row order picks the wrong value.
    """
    from app.models.document_extraction import DocumentExtraction

    doc = _make_doc(db, workspace, user, "latest attempt corpus")
    db.add(
        DocumentExtraction(
            id=str(uuid.uuid4()),
            document_id=doc.id,
            workspace_id=workspace.id,
            field_name="grantor",
            field_value="Corrected Name",
            field_type="text",
            confidence=1.0,
            attempt=3,
        )
    )
    db.commit()
    db.add(
        DocumentExtraction(
            id=str(uuid.uuid4()),
            document_id=doc.id,
            workspace_id=workspace.id,
            field_name="grantor",
            field_value="Stale Name",
            field_type="text",
            confidence=0.4,
            attempt=1,
        )
    )
    db.commit()

    results = run_search(
        workspace.id,
        {"fts_query": "latest attempt corpus", "field_filters": [], "doc_type_filter": None},
        db,
        mode="keyword",
    )
    assert len(results) == 1
    assert results[0]["matched_fields"]["grantor"] == "Corrected Name"


def test_run_search_semantic_mode_without_openai_key_returns_empty(
    monkeypatch, auth_headers, client
):
    """mode='semantic' with no OpenAI key configured returns empty results without error."""
    from app.config import settings

    monkeypatch.setattr(settings, "openai_api_key", None)
    ws_resp = client.post(
        "/workspaces/",
        json={"name": "semantic-no-key", "vertical": "general"},
        headers=auth_headers,
    )
    workspace_id = ws_resp.json()["id"]

    mock_client = MagicMock()
    mock_client.messages.create.return_value = MagicMock(
        content=[
            MagicMock(
                text='{"fts_query": "property", "field_filters": [], "doc_type_filter": null}'
            )
        ]
    )
    with patch("app.services.claude_client.get_client", return_value=mock_client):
        response = client.post(
            f"/workspaces/{workspace_id}/search/",
            json={"query": "property", "mode": "semantic"},
            headers=auth_headers,
        )
    assert response.status_code == 200
    assert response.json()["results"] == []
