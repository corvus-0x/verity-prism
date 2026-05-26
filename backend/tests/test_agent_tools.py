import pytest
from sqlalchemy import text
from app.models.user import User
from app.models.workspace import Workspace
from app.models.document import Document
from app.services.agent_tools import search_documents, execute, get_entity
import uuid


@pytest.fixture
def user(db):
    u = User(
        id=str(uuid.uuid4()),
        email=f"test_{uuid.uuid4().hex[:8]}@example.com",
        password_hash="hashed",
        full_name="Test User",
    )
    db.add(u)
    db.commit()
    return u


@pytest.fixture
def workspace(db, user):
    ws = Workspace(id=str(uuid.uuid4()), name="Test WS", vertical="fraud", created_by=user.id)
    db.add(ws)
    db.commit()
    return ws


@pytest.fixture
def document(db, workspace, user):
    doc = Document(
        id=str(uuid.uuid4()),
        workspace_id=workspace.id,
        filename="test_deed.pdf",
        original_filename="test_deed.pdf",
        file_path="/uploads/test_deed.pdf",
        file_type="pdf",
        sha256_hash="a" * 64,
        uploaded_by=user.id,
        detected_doc_type="DEED",
        is_deleted=False,
    )
    db.add(doc)
    db.commit()
    # Manually populate search_vector so FTS queries work in tests
    db.execute(
        text("UPDATE documents SET search_vector = to_tsvector('english', :content) WHERE id = :id"),
        {"content": "grantor smith deed property transfer", "id": doc.id},
    )
    db.commit()
    return doc


def test_search_documents_no_filter_returns_workspace_docs(db, workspace, document):
    result = search_documents(workspace_id=workspace.id, db=db, query="")
    assert result["count"] == 1
    assert result["documents"][0]["filename"] == "test_deed.pdf"


def test_search_documents_doc_type_filter(db, workspace, document):
    result = search_documents(workspace_id=workspace.id, db=db, query="", doc_type="DEED")
    assert result["count"] == 1

    result_miss = search_documents(workspace_id=workspace.id, db=db, query="", doc_type="990")
    assert result_miss["count"] == 0


def test_search_documents_fts(db, workspace, document):
    result = search_documents(workspace_id=workspace.id, db=db, query="grantor smith")
    assert result["count"] == 1

    result_miss = search_documents(workspace_id=workspace.id, db=db, query="unrelated xyz")
    assert result_miss["count"] == 0


def test_search_documents_workspace_isolation(db, workspace, document, user):
    other_ws = Workspace(id=str(uuid.uuid4()), name="Other WS", vertical="fraud", created_by=user.id)
    db.add(other_ws)
    db.commit()
    result = search_documents(workspace_id=other_ws.id, db=db, query="")
    assert result["count"] == 0


def test_execute_unknown_tool_returns_error(db, workspace):
    result = execute("nonexistent_tool", workspace.id, db, {})
    assert "error" in result


@pytest.fixture
def entity(db, workspace, user):
    from app.models.entity import Entity
    e = Entity(
        id=str(uuid.uuid4()),
        workspace_id=workspace.id,
        name="Do Good In His Name Inc",
        type="organization",
        status="active",
        data={"ein": "12-3456789"},
        is_deleted=False,
        created_by=user.id,
    )
    db.add(e)
    db.commit()
    return e


def test_get_entity_exact_match(db, workspace, entity):
    result = get_entity(workspace_id=workspace.id, db=db, name="Do Good In His Name Inc")
    assert result["entity"]["name"] == "Do Good In His Name Inc"
    assert result["entity"]["data"]["ein"] == "12-3456789"


def test_get_entity_partial_match(db, workspace, entity):
    result = get_entity(workspace_id=workspace.id, db=db, name="Do Good")
    assert result["entity"]["name"] == "Do Good In His Name Inc"


def test_get_entity_not_found(db, workspace):
    result = get_entity(workspace_id=workspace.id, db=db, name="Nonexistent LLC")
    assert result["entity"] is None


def test_get_entity_multiple_matches_returns_list(db, workspace, entity, user):
    from app.models.entity import Entity
    e2 = Entity(
        id=str(uuid.uuid4()),
        workspace_id=workspace.id,
        name="Do Good Foundation",
        type="organization",
        status="active",
        is_deleted=False,
        created_by=user.id,
    )
    db.add(e2)
    db.commit()
    result = get_entity(workspace_id=workspace.id, db=db, name="Do Good")
    assert "entities" in result
    assert len(result["entities"]) == 2
    # Multi-match response has no data field — just id, name, type, status
    assert "data" not in result["entities"][0]


def test_get_entity_workspace_isolation(db, workspace, entity, user):
    other_ws = Workspace(id=str(uuid.uuid4()), name="Other WS", vertical="fraud", created_by=user.id)
    db.add(other_ws)
    db.commit()
    result = get_entity(workspace_id=other_ws.id, db=db, name="Do Good")
    assert result["entity"] is None
