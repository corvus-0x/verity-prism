import pytest
from sqlalchemy import text
from app.models.user import User
from app.models.workspace import Workspace
from app.models.document import Document
from app.services.agent_tools import search_documents, execute, get_entity, query_extractions, get_transactions
from app.models.document_extraction import DocumentExtraction
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


def test_get_entity_case_insensitive(db, workspace, user):
    from app.models.entity import Entity
    e = Entity(
        id=str(uuid.uuid4()),
        workspace_id=workspace.id,
        name="Do Good In His Name Inc",
        type="organization",
        status="active",
        is_deleted=False,
        created_by=user.id,
    )
    db.add(e)
    db.commit()
    result = get_entity(workspace_id=workspace.id, db=db, name="do good in his name")
    assert result["entity"]["name"] == "Do Good In His Name Inc"


def test_get_entity_excludes_soft_deleted(db, workspace, user):
    from app.models.entity import Entity
    deleted = Entity(
        id=str(uuid.uuid4()),
        workspace_id=workspace.id,
        name="Do Good Deleted Org",
        type="organization",
        status="active",
        is_deleted=True,
        created_by=user.id,
    )
    db.add(deleted)
    db.commit()
    result = get_entity(workspace_id=workspace.id, db=db, name="Do Good Deleted")
    assert result["entity"] is None


@pytest.fixture
def extraction(db, workspace, document, user):
    ext = DocumentExtraction(
        id=str(uuid.uuid4()),
        document_id=document.id,
        workspace_id=workspace.id,
        field_name="grantor",
        field_value="John Smith",
        field_type="text",
        confidence=0.95,
    )
    db.add(ext)
    amt = DocumentExtraction(
        id=str(uuid.uuid4()),
        document_id=document.id,
        workspace_id=workspace.id,
        field_name="consideration_amount",
        field_value="250000",
        field_type="text",
        confidence=0.9,
    )
    db.add(amt)
    db.commit()
    return ext


def test_query_extractions_eq(db, workspace, extraction):
    result = query_extractions(
        workspace_id=workspace.id, db=db,
        field_name="grantor", operator="eq", value="John Smith"
    )
    assert result["count"] == 1
    assert result["extractions"][0]["field_value"] == "John Smith"
    assert result["extractions"][0]["filename"] == "test_deed.pdf"
    assert result["extractions"][0]["doc_type"] == "DEED"


def test_query_extractions_contains(db, workspace, extraction):
    result = query_extractions(
        workspace_id=workspace.id, db=db,
        field_name="grantor", operator="contains", value="Smith"
    )
    assert result["count"] == 1
    assert result["extractions"][0]["filename"] == "test_deed.pdf"
    assert result["extractions"][0]["doc_type"] == "DEED"


def test_query_extractions_gt(db, workspace, extraction):
    result = query_extractions(
        workspace_id=workspace.id, db=db,
        field_name="consideration_amount", operator="gt", value="100000"
    )
    assert result["count"] == 1

    result_miss = query_extractions(
        workspace_id=workspace.id, db=db,
        field_name="consideration_amount", operator="gt", value="500000"
    )
    assert result_miss["count"] == 0


def test_query_extractions_lt(db, workspace, extraction):
    result = query_extractions(
        workspace_id=workspace.id, db=db,
        field_name="consideration_amount", operator="lt", value="500000"
    )
    assert result["count"] == 1


def test_query_extractions_no_match(db, workspace, extraction):
    result = query_extractions(
        workspace_id=workspace.id, db=db,
        field_name="grantor", operator="eq", value="Nobody"
    )
    assert result["count"] == 0


from app.models.transaction import Transaction
from decimal import Decimal


@pytest.fixture
def transaction(db, workspace, user):
    t = Transaction(
        id=str(uuid.uuid4()),
        workspace_id=workspace.id,
        transaction_type="purchase",
        amount_paid=Decimal("300000"),
        appraised_value=Decimal("200000"),
        instrument_number="2021-12345",
        created_by=user.id,
    )
    db.add(t)
    db.commit()
    return t


def test_get_transactions_no_filter(db, workspace, transaction):
    result = get_transactions(workspace_id=workspace.id, db=db)
    assert result["count"] == 1
    assert result["transactions"][0]["instrument_number"] == "2021-12345"


def test_get_transactions_overpay_pct_calculated(db, workspace, transaction):
    result = get_transactions(workspace_id=workspace.id, db=db)
    assert result["transactions"][0]["overpay_pct"] == 50.0


def test_get_transactions_min_amount_filter(db, workspace, transaction):
    result = get_transactions(workspace_id=workspace.id, db=db, min_amount=250000)
    assert result["count"] == 1

    result_miss = get_transactions(workspace_id=workspace.id, db=db, min_amount=400000)
    assert result_miss["count"] == 0


def test_get_transactions_max_amount_filter(db, workspace, transaction):
    result = get_transactions(workspace_id=workspace.id, db=db, max_amount=400000)
    assert result["count"] == 1

    result_miss = get_transactions(workspace_id=workspace.id, db=db, max_amount=100000)
    assert result_miss["count"] == 0


def test_get_transactions_type_filter(db, workspace, transaction):
    result = get_transactions(workspace_id=workspace.id, db=db, transaction_type="purchase")
    assert result["count"] == 1

    result_miss = get_transactions(workspace_id=workspace.id, db=db, transaction_type="sale")
    assert result_miss["count"] == 0


def test_get_transactions_zero_amount_serializes_as_string(db, workspace, user):
    t = Transaction(
        id=str(uuid.uuid4()),
        workspace_id=workspace.id,
        transaction_type="purchase",
        amount_paid=Decimal("0"),
        appraised_value=Decimal("200000"),
        instrument_number="2021-zero",
        created_by=user.id,
    )
    db.add(t)
    db.commit()
    result = get_transactions(workspace_id=workspace.id, db=db)
    txn = next(r for r in result["transactions"] if r["instrument_number"] == "2021-zero")
    assert float(txn["amount_paid"]) == 0.0  # stored as 0.00 by Postgres; Decimal("0") is falsy — must use is not None
    assert txn["overpay_pct"] == -100.0  # (0 - 200000) / 200000 * 100 = -100.0


from app.services.agent_tools import get_findings, get_leads
from app.models.finding import Finding
from app.models.lead import InvestigationLead


def test_get_findings_returns_all(db, workspace, user):
    f = Finding(
        id=str(uuid.uuid4()),
        workspace_id=workspace.id,
        title="Overpayment Pattern",
        severity="high",
        status="open",
        description="Consistent above-market transactions",
        created_by=user.id,
    )
    db.add(f)
    db.commit()
    result = get_findings(workspace_id=workspace.id, db=db)
    assert result["count"] == 1
    assert result["findings"][0]["title"] == "Overpayment Pattern"
    assert result["findings"][0]["severity"] == "high"


def test_get_findings_empty(db, workspace):
    result = get_findings(workspace_id=workspace.id, db=db)
    assert result["count"] == 0
    assert result["findings"] == []


def test_get_leads_pending_by_default(db, workspace, user):
    lead = InvestigationLead(
        id=str(uuid.uuid4()),
        workspace_id=workspace.id,
        question="Who are the grantees in all deeds?",
        status="pending",
        originated_by="ai",
        source="ai",
    )
    done = InvestigationLead(
        id=str(uuid.uuid4()),
        workspace_id=workspace.id,
        question="Completed lead",
        status="complete",
        originated_by="user",
    )
    db.add(lead)
    db.add(done)
    db.commit()
    result = get_leads(workspace_id=workspace.id, db=db)
    assert result["count"] == 1
    assert result["leads"][0]["status"] == "pending"
    assert result["leads"][0]["source"] == "ai"


def test_get_leads_all_status(db, workspace, user):
    for status in ("pending", "in_progress", "complete"):
        db.add(InvestigationLead(
            id=str(uuid.uuid4()),
            workspace_id=workspace.id,
            question=f"Lead {status}",
            status=status,
            originated_by="user",
            source="user",
        ))
    db.commit()
    result = get_leads(workspace_id=workspace.id, db=db, status="all")
    assert result["count"] == 3
    assert all(lead["source"] == "user" for lead in result["leads"])
