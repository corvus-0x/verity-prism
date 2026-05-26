# Tool-Use Chat Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the single-call `ai_engine.chat()` with a native Anthropic tool-use agentic loop that gives Claude 6 read-only tools to query workspace data, capped at 10 rounds with a synthesis pass fallback.

**Architecture:** `ai_engine.py` owns the loop — it builds the message list, calls Claude with tool schemas, dispatches tool calls to `agent_tools.py`, and repeats until `end_turn` or 10 rounds. `agent_registry.py` owns the JSON schemas and the vertical → tool list mapping so future verticals can extend the tool set without touching the loop. The router and frontend are unchanged; `chat()` still returns a plain string.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.0, Anthropic SDK (native tool use), pytest, PostgreSQL 16

---

## File Map

| File | Status | Responsibility |
|------|--------|---------------|
| `backend/app/services/agent_tools.py` | CREATE | 6 tool functions + `execute()` dispatcher |
| `backend/app/services/agent_registry.py` | CREATE | Tool JSON schemas + `get_tools_for_vertical()` |
| `backend/app/services/ai_engine.py` | MODIFY | Replace `chat()` with agentic loop; add `_synthesis_pass()`, `_extract_text()` |
| `backend/tests/test_agent_tools.py` | CREATE | Unit tests for all 6 tools + dispatcher |
| `backend/tests/test_ai.py` | MODIFY | Update mocks for `stop_reason` + new loop behavior |

---

## Task 1: Scaffold agent_tools.py and implement search_documents

**Files:**
- Create: `backend/app/services/agent_tools.py`
- Create: `backend/tests/test_agent_tools.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_agent_tools.py`:

```python
import pytest
from sqlalchemy import text
from app.models.workspace import Workspace
from app.models.document import Document
from app.services.agent_tools import search_documents, execute
import uuid


@pytest.fixture
def workspace(db):
    ws = Workspace(id=str(uuid.uuid4()), name="Test WS", vertical="fraud")
    db.add(ws)
    db.commit()
    return ws


@pytest.fixture
def document(db, workspace):
    doc = Document(
        id=str(uuid.uuid4()),
        workspace_id=workspace.id,
        filename="test_deed.pdf",
        original_filename="test_deed.pdf",
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


def test_search_documents_workspace_isolation(db, workspace, document):
    other_ws = Workspace(id=str(uuid.uuid4()), name="Other WS", vertical="fraud")
    db.add(other_ws)
    db.commit()
    result = search_documents(workspace_id=other_ws.id, db=db, query="")
    assert result["count"] == 0


def test_execute_unknown_tool_returns_error(db, workspace):
    result = execute("nonexistent_tool", workspace.id, db, {})
    assert "error" in result
```

- [ ] **Step 2: Run tests to confirm they fail**

```
cd backend
pytest tests/test_agent_tools.py -v
```

Expected: `ModuleNotFoundError` or `ImportError` — `agent_tools` does not exist yet.

- [ ] **Step 3: Create agent_tools.py with scaffold and search_documents**

Create `backend/app/services/agent_tools.py`:

```python
import logging
from sqlalchemy.orm import Session
from sqlalchemy import text as sql_text
from app.models.document import Document
from app.models.document_extraction import DocumentExtraction
from app.models.entity import Entity
from app.models.transaction import Transaction
from app.models.finding import Finding
from app.models.lead import InvestigationLead

logger = logging.getLogger(__name__)


def search_documents(
    workspace_id: str, db: Session, query: str, doc_type: str = None
) -> dict:
    """Search workspace documents by keyword with optional doc_type filter.
    Returns up to 10 docs with up to 5 extracted fields each.
    workspace_id is always injected by execute() — never from Claude's input.
    """
    q = db.query(Document).filter(
        Document.workspace_id == workspace_id,
        Document.is_deleted == False,
    )
    if query:
        q = q.filter(
            sql_text("search_vector @@ plainto_tsquery('english', :query)").bindparams(
                query=query
            )
        )
    if doc_type:
        q = q.filter(Document.detected_doc_type == doc_type)

    docs = q.limit(10).all()
    results = []
    for doc in docs:
        extractions = (
            db.query(DocumentExtraction)
            .filter(DocumentExtraction.document_id == doc.id)
            .limit(5)
            .all()
        )
        results.append({
            "id": doc.id,
            "filename": doc.filename,
            "doc_type": doc.detected_doc_type,
            "matched_fields": {e.field_name: e.field_value for e in extractions},
        })
    return {"documents": results, "count": len(results)}


def get_entity(workspace_id: str, db: Session, name: str) -> dict:
    pass  # implemented in Task 2


def query_extractions(
    workspace_id: str, db: Session, field_name: str, operator: str, value: str
) -> dict:
    pass  # implemented in Task 3


def get_transactions(
    workspace_id: str,
    db: Session,
    min_amount: float = None,
    max_amount: float = None,
    transaction_type: str = None,
) -> dict:
    pass  # implemented in Task 4


def get_findings(workspace_id: str, db: Session) -> dict:
    pass  # implemented in Task 5


def get_leads(workspace_id: str, db: Session, status: str = "pending") -> dict:
    pass  # implemented in Task 5


def execute(tool_name: str, workspace_id: str, db: Session, params: dict) -> dict:
    """Dispatch a tool call by name.
    workspace_id is always injected here — it is never a parameter Claude can pass.
    """
    _tools = {
        "search_documents": search_documents,
        "get_entity": get_entity,
        "query_extractions": query_extractions,
        "get_transactions": get_transactions,
        "get_findings": get_findings,
        "get_leads": get_leads,
    }
    fn = _tools.get(tool_name)
    if fn is None:
        return {"error": f"Unknown tool: {tool_name}"}
    try:
        return fn(workspace_id=workspace_id, db=db, **params)
    except Exception as e:
        logger.warning("Tool %s failed: %s", tool_name, e)
        return {"error": str(e)}
```

- [ ] **Step 4: Run search_documents tests to confirm they pass**

```
cd backend
pytest tests/test_agent_tools.py::test_search_documents_no_filter_returns_workspace_docs tests/test_agent_tools.py::test_search_documents_doc_type_filter tests/test_agent_tools.py::test_search_documents_fts tests/test_agent_tools.py::test_search_documents_workspace_isolation tests/test_agent_tools.py::test_execute_unknown_tool_returns_error -v
```

Expected: all 5 PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/agent_tools.py backend/tests/test_agent_tools.py
git commit -m "feat: agent_tools scaffold — search_documents + execute dispatcher"
```

---

## Task 2: Implement get_entity

**Files:**
- Modify: `backend/app/services/agent_tools.py`
- Modify: `backend/tests/test_agent_tools.py`

- [ ] **Step 1: Add failing tests**

Append to `backend/tests/test_agent_tools.py`:

```python
from app.services.agent_tools import get_entity


@pytest.fixture
def entity(db, workspace):
    from app.models.entity import Entity
    e = Entity(
        id=str(uuid.uuid4()),
        workspace_id=workspace.id,
        name="Do Good In His Name Inc",
        type="organization",
        status="active",
        data={"ein": "12-3456789"},
        is_deleted=False,
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


def test_get_entity_multiple_matches_returns_list(db, workspace, entity):
    from app.models.entity import Entity
    e2 = Entity(
        id=str(uuid.uuid4()),
        workspace_id=workspace.id,
        name="Do Good Foundation",
        type="organization",
        status="active",
        is_deleted=False,
    )
    db.add(e2)
    db.commit()
    result = get_entity(workspace_id=workspace.id, db=db, name="Do Good")
    assert "entities" in result
    assert len(result["entities"]) == 2
    # Multi-match response has no data field — just id, name, type, status
    assert "data" not in result["entities"][0]


def test_get_entity_workspace_isolation(db, workspace, entity):
    other_ws = Workspace(id=str(uuid.uuid4()), name="Other WS", vertical="fraud")
    db.add(other_ws)
    db.commit()
    result = get_entity(workspace_id=other_ws.id, db=db, name="Do Good")
    assert result["entity"] is None
```

- [ ] **Step 2: Run tests to confirm they fail**

```
cd backend
pytest tests/test_agent_tools.py::test_get_entity_exact_match -v
```

Expected: FAIL — `get_entity` returns `None` (stub).

- [ ] **Step 3: Implement get_entity**

Replace the `get_entity` stub in `backend/app/services/agent_tools.py`:

```python
def get_entity(workspace_id: str, db: Session, name: str) -> dict:
    """Look up entities by name (partial match). Returns full data for one match,
    summary list for multiple matches, null if none found.
    """
    matches = (
        db.query(Entity)
        .filter(
            Entity.workspace_id == workspace_id,
            Entity.is_deleted == False,
            Entity.name.ilike(f"%{name}%"),
        )
        .limit(5)
        .all()
    )
    if not matches:
        return {"entity": None}
    if len(matches) == 1:
        e = matches[0]
        return {
            "entity": {
                "id": e.id,
                "name": e.name,
                "type": e.type,
                "status": e.status,
                "data": e.data or {},
            }
        }
    return {
        "entities": [
            {"id": e.id, "name": e.name, "type": e.type, "status": e.status}
            for e in matches
        ]
    }
```

- [ ] **Step 4: Run get_entity tests to confirm they pass**

```
cd backend
pytest tests/test_agent_tools.py -k "entity" -v
```

Expected: all 5 PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/agent_tools.py backend/tests/test_agent_tools.py
git commit -m "feat: agent_tools — get_entity"
```

---

## Task 3: Implement query_extractions

**Files:**
- Modify: `backend/app/services/agent_tools.py`
- Modify: `backend/tests/test_agent_tools.py`

- [ ] **Step 1: Add failing tests**

Append to `backend/tests/test_agent_tools.py`:

```python
from app.services.agent_tools import query_extractions
from app.models.document_extraction import DocumentExtraction


@pytest.fixture
def extraction(db, workspace, document):
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


def test_query_extractions_contains(db, workspace, extraction):
    result = query_extractions(
        workspace_id=workspace.id, db=db,
        field_name="grantor", operator="contains", value="Smith"
    )
    assert result["count"] == 1


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
```

- [ ] **Step 2: Run tests to confirm they fail**

```
cd backend
pytest tests/test_agent_tools.py::test_query_extractions_eq -v
```

Expected: FAIL — `query_extractions` returns `None` (stub).

- [ ] **Step 3: Implement query_extractions**

Replace the `query_extractions` stub in `backend/app/services/agent_tools.py`:

```python
def query_extractions(
    workspace_id: str, db: Session, field_name: str, operator: str, value: str
) -> dict:
    """Query document_extractions by field name and value. Operators: eq, contains, gt, lt.
    Returns up to 50 matching rows with document_id, field_name, field_value.
    """
    q = db.query(DocumentExtraction).filter(
        DocumentExtraction.workspace_id == workspace_id,
        DocumentExtraction.field_name == field_name,
        DocumentExtraction.field_value.isnot(None),
    )
    if operator == "eq":
        q = q.filter(DocumentExtraction.field_value == value)
    elif operator == "contains":
        q = q.filter(DocumentExtraction.field_value.ilike(f"%{value}%"))
    elif operator in ("gt", "lt"):
        numeric_guard = sql_text("field_value ~ '^[0-9]+(\\.[0-9]+)?$'")
        comparator = ">" if operator == "gt" else "<"
        q = q.filter(
            numeric_guard,
            sql_text(f"CAST(field_value AS NUMERIC) {comparator} :val").bindparams(
                val=float(value)
            ),
        )

    rows = q.limit(50).all()
    return {
        "extractions": [
            {
                "document_id": r.document_id,
                "field_name": r.field_name,
                "field_value": r.field_value,
            }
            for r in rows
        ],
        "count": len(rows),
    }
```

- [ ] **Step 4: Run query_extractions tests to confirm they pass**

```
cd backend
pytest tests/test_agent_tools.py -k "extractions" -v
```

Expected: all 5 PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/agent_tools.py backend/tests/test_agent_tools.py
git commit -m "feat: agent_tools — query_extractions"
```

---

## Task 4: Implement get_transactions

**Files:**
- Modify: `backend/app/services/agent_tools.py`
- Modify: `backend/tests/test_agent_tools.py`

- [ ] **Step 1: Add failing tests**

Append to `backend/tests/test_agent_tools.py`:

```python
from app.services.agent_tools import get_transactions
from app.models.transaction import Transaction
from decimal import Decimal


@pytest.fixture
def transaction(db, workspace):
    t = Transaction(
        id=str(uuid.uuid4()),
        workspace_id=workspace.id,
        transaction_type="purchase",
        amount_paid=Decimal("300000"),
        appraised_value=Decimal("200000"),
        instrument_number="2021-12345",
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
```

- [ ] **Step 2: Run tests to confirm they fail**

```
cd backend
pytest tests/test_agent_tools.py::test_get_transactions_no_filter -v
```

Expected: FAIL — `get_transactions` returns `None` (stub).

- [ ] **Step 3: Implement get_transactions**

Replace the `get_transactions` stub in `backend/app/services/agent_tools.py`:

```python
def get_transactions(
    workspace_id: str,
    db: Session,
    min_amount: float = None,
    max_amount: float = None,
    transaction_type: str = None,
) -> dict:
    """Filter transactions by amount range and/or type.
    Returns up to 50 matching records with overpay percentage calculated.
    """
    q = db.query(Transaction).filter(Transaction.workspace_id == workspace_id)
    if transaction_type:
        q = q.filter(Transaction.transaction_type == transaction_type)
    if min_amount is not None:
        q = q.filter(Transaction.amount_paid >= min_amount)
    if max_amount is not None:
        q = q.filter(Transaction.amount_paid <= max_amount)

    rows = q.limit(50).all()
    results = []
    for t in rows:
        overpay_pct = None
        if t.amount_paid and t.appraised_value and float(t.appraised_value) > 0:
            overpay_pct = round(
                (
                    (float(t.amount_paid) - float(t.appraised_value))
                    / float(t.appraised_value)
                )
                * 100,
                1,
            )
        results.append({
            "id": t.id,
            "transaction_type": t.transaction_type,
            "amount_paid": str(t.amount_paid) if t.amount_paid else None,
            "appraised_value": str(t.appraised_value) if t.appraised_value else None,
            "overpay_pct": overpay_pct,
            "transaction_date": str(t.transaction_date) if t.transaction_date else None,
            "instrument_number": t.instrument_number,
            "notes": t.notes,
        })
    return {"transactions": results, "count": len(results)}
```

- [ ] **Step 4: Run get_transactions tests to confirm they pass**

```
cd backend
pytest tests/test_agent_tools.py -k "transactions" -v
```

Expected: all 5 PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/agent_tools.py backend/tests/test_agent_tools.py
git commit -m "feat: agent_tools — get_transactions"
```

---

## Task 5: Implement get_findings and get_leads

**Files:**
- Modify: `backend/app/services/agent_tools.py`
- Modify: `backend/tests/test_agent_tools.py`

- [ ] **Step 1: Add failing tests**

Append to `backend/tests/test_agent_tools.py`:

```python
from app.services.agent_tools import get_findings, get_leads
from app.models.finding import Finding
from app.models.lead import InvestigationLead


def test_get_findings_returns_all(db, workspace):
    f = Finding(
        id=str(uuid.uuid4()),
        workspace_id=workspace.id,
        title="Overpayment Pattern",
        severity="high",
        status="open",
        description="Consistent above-market transactions",
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


def test_get_leads_pending_by_default(db, workspace):
    lead = InvestigationLead(
        id=str(uuid.uuid4()),
        workspace_id=workspace.id,
        question="Who are the grantees in all deeds?",
        status="pending",
        source="ai",
    )
    done = InvestigationLead(
        id=str(uuid.uuid4()),
        workspace_id=workspace.id,
        question="Completed lead",
        status="completed",
        source="user",
    )
    db.add(lead)
    db.add(done)
    db.commit()
    result = get_leads(workspace_id=workspace.id, db=db)
    assert result["count"] == 1
    assert result["leads"][0]["status"] == "pending"


def test_get_leads_all_status(db, workspace):
    for status in ("pending", "in_progress", "completed"):
        db.add(InvestigationLead(
            id=str(uuid.uuid4()),
            workspace_id=workspace.id,
            question=f"Lead {status}",
            status=status,
            source="user",
        ))
    db.commit()
    result = get_leads(workspace_id=workspace.id, db=db, status="all")
    assert result["count"] == 3
```

- [ ] **Step 2: Run tests to confirm they fail**

```
cd backend
pytest tests/test_agent_tools.py::test_get_findings_returns_all -v
```

Expected: FAIL — `get_findings` returns `None` (stub).

- [ ] **Step 3: Implement get_findings and get_leads**

Replace both stubs in `backend/app/services/agent_tools.py`:

```python
def get_findings(workspace_id: str, db: Session) -> dict:
    """List all findings in the workspace with title, severity, status, and description."""
    findings = db.query(Finding).filter(Finding.workspace_id == workspace_id).all()
    return {
        "findings": [
            {
                "id": f.id,
                "title": f.title,
                "severity": f.severity,
                "status": f.status,
                "description": f.description,
            }
            for f in findings
        ],
        "count": len(findings),
    }


def get_leads(workspace_id: str, db: Session, status: str = "pending") -> dict:
    """List investigation leads filtered by status (pending, in_progress, or all)."""
    q = db.query(InvestigationLead).filter(InvestigationLead.workspace_id == workspace_id)
    if status != "all":
        q = q.filter(InvestigationLead.status == status)
    leads = q.all()
    return {
        "leads": [
            {
                "id": lead.id,
                "question": lead.question,
                "status": lead.status,
                "source": lead.source,
            }
            for lead in leads
        ],
        "count": len(leads),
    }
```

- [ ] **Step 4: Run all agent_tools tests to confirm full suite passes**

```
cd backend
pytest tests/test_agent_tools.py -v
```

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/agent_tools.py backend/tests/test_agent_tools.py
git commit -m "feat: agent_tools — get_findings, get_leads, full suite green"
```

---

## Task 6: Create agent_registry.py

**Files:**
- Create: `backend/app/services/agent_registry.py`

No DB interaction — pure data structure. No separate test file needed; the schema structure is exercised through the ai_engine tests in Task 7.

- [ ] **Step 1: Create agent_registry.py**

Create `backend/app/services/agent_registry.py`:

```python
"""
Tool schema registry — maps vertical names to their tool lists.
Core tools are always available. Add vertical-specific tools by extending
VERTICAL_TOOLS[<vertical>] with tool schemas from agent_tools_<vertical>.py.
"""


def build_tool_schemas() -> list[dict]:
    """Return the JSON schemas for all 6 core tools.
    These descriptions are a design artifact — Claude uses them to decide which tool to call.
    """
    return [
        {
            "name": "search_documents",
            "description": (
                "Search workspace documents by keyword and optionally filter by document type. "
                "Returns up to 10 matching documents with filename, type, and top matched fields."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Keyword search string",
                    },
                    "doc_type": {
                        "type": "string",
                        "description": "Optional document type filter (DEED, 990, UCC, SOS-FILING, etc.)",
                    },
                },
                "required": ["query"],
            },
        },
        {
            "name": "get_entity",
            "description": (
                "Look up a specific entity (person, LLC, organization) by name. "
                "Returns the entity record and all associated data fields."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Entity name to look up (exact or partial match)",
                    },
                },
                "required": ["name"],
            },
        },
        {
            "name": "query_extractions",
            "description": (
                "Find documents where a specific extracted field matches a value. "
                "Use for precise field-level queries like 'all deeds where grantor contains Smith' "
                "or 'documents where consideration_amount is greater than 500000'."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "field_name": {
                        "type": "string",
                        "description": "The extracted field name to filter on",
                    },
                    "operator": {
                        "type": "string",
                        "enum": ["eq", "contains", "gt", "lt"],
                        "description": "Comparison operator",
                    },
                    "value": {
                        "type": "string",
                        "description": "Value to compare against (always a string, even for numeric comparisons)",
                    },
                },
                "required": ["field_name", "operator", "value"],
            },
        },
        {
            "name": "get_transactions",
            "description": (
                "Filter workspace transactions by amount range and/or transaction type. "
                "Returns amount paid, appraised value, overpay percentage, date, and instrument number."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "min_amount": {
                        "type": "number",
                        "description": "Minimum transaction amount",
                    },
                    "max_amount": {
                        "type": "number",
                        "description": "Maximum transaction amount",
                    },
                    "transaction_type": {
                        "type": "string",
                        "description": "Filter by transaction type",
                    },
                },
                "required": [],
            },
        },
        {
            "name": "get_findings",
            "description": (
                "List all findings in the workspace with title, severity, and status. "
                "Check this before making new observations to avoid duplicating what is already recorded."
            ),
            "input_schema": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
        {
            "name": "get_leads",
            "description": (
                "List investigation leads filtered by status. "
                "Check this before suggesting new leads to avoid duplicating what is already being tracked."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "enum": ["pending", "in_progress", "all"],
                        "description": "Filter by lead status. Defaults to pending.",
                    },
                },
                "required": [],
            },
        },
    ]


VERTICAL_TOOLS: dict[str, list[dict]] = {
    "fraud": build_tool_schemas(),
    "insurance": build_tool_schemas(),
    "general": build_tool_schemas(),
}


def get_tools_for_vertical(vertical: str) -> list[dict]:
    """Return tool schemas for the given vertical.
    Falls back to core tools if vertical is not registered.
    To add vertical-specific tools: extend VERTICAL_TOOLS[vertical] with additional schemas.
    """
    return VERTICAL_TOOLS.get(vertical, build_tool_schemas())
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/services/agent_registry.py
git commit -m "feat: agent_registry — tool schemas + vertical registry"
```

---

## Task 7: Replace ai_engine.chat() with agentic loop

**Files:**
- Modify: `backend/app/services/ai_engine.py`
- Modify: `backend/tests/test_ai.py`

- [ ] **Step 1: Update test_ai.py mocks for the new loop**

The existing mocks set `content=[MagicMock(text="...")]` but don't set `stop_reason`. The new loop checks `response.stop_reason` and iterates `response.content` checking `block.type`. Update all three tests in `backend/tests/test_ai.py`:

```python
import pytest
from unittest.mock import patch, MagicMock


@pytest.fixture
def workspace_id(client, auth_headers):
    return client.post(
        "/workspaces/",
        json={"name": "Test Workspace", "vertical": "fraud"},
        headers=auth_headers,
    ).json()["id"]


def _mock_end_turn(text: str) -> MagicMock:
    """Build a mock Claude response that ends immediately with text."""
    block = MagicMock()
    block.type = "text"
    block.text = text
    response = MagicMock()
    response.stop_reason = "end_turn"
    response.content = [block]
    return response


def test_create_conversation(client, auth_headers, workspace_id):
    response = client.post(
        f"/workspaces/{workspace_id}/conversations", headers=auth_headers
    )
    assert response.status_code == 201
    assert response.json()["workspace_id"] == workspace_id


def test_send_message_returns_assistant_response(client, auth_headers, workspace_id):
    conv = client.post(
        f"/workspaces/{workspace_id}/conversations", headers=auth_headers
    ).json()

    with patch("app.services.ai_engine.client") as mock_client:
        mock_client.messages.create.return_value = _mock_end_turn(
            "Based on the workspace data, I found relevant records."
        )
        response = client.post(
            f"/workspaces/{workspace_id}/conversations/{conv['id']}/messages",
            json={"content": "What documents are in this workspace?"},
            headers=auth_headers,
        )

    assert response.status_code == 201
    data = response.json()
    assert data["role"] == "assistant"
    assert len(data["content"]) > 0


def test_conversation_title_set_from_first_message(client, auth_headers, workspace_id):
    conv = client.post(
        f"/workspaces/{workspace_id}/conversations", headers=auth_headers
    ).json()
    assert conv["title"] is None

    with patch("app.services.ai_engine.client") as mock_client:
        mock_client.messages.create.return_value = _mock_end_turn("Here is what I found.")
        client.post(
            f"/workspaces/{workspace_id}/conversations/{conv['id']}/messages",
            json={"content": "What entities are in this workspace?"},
            headers=auth_headers,
        )

    updated = client.get(
        f"/workspaces/{workspace_id}/conversations", headers=auth_headers
    ).json()
    conv_updated = next(c for c in updated if c["id"] == conv["id"])
    assert conv_updated["title"] is not None
```

Note: the patch target changes from `app.services.ai_engine.Anthropic` to `app.services.ai_engine.client` — the new `ai_engine.py` instantiates the client at module level, so patching the instance directly is cleaner.

- [ ] **Step 2: Run existing tests to confirm they currently pass (before modifying ai_engine)**

```
cd backend
pytest tests/test_ai.py -v
```

Expected: all 3 tests PASS (with updated mocks but old ai_engine — they'll fail because the mock target changed). If they fail with "stop_reason" errors, that's expected — move to Step 3.

- [ ] **Step 3: Replace ai_engine.py**

Overwrite `backend/app/services/ai_engine.py` with:

```python
"""
AI Chat Engine — Claude with native tool use.

chat() runs an agentic loop: Claude calls tools to query workspace data,
results are injected back as tool_result blocks, and the loop repeats until
end_turn or MAX_TOOL_ROUNDS. A synthesis pass handles the round-limit case.
Message persistence is the router's responsibility — chat() returns a plain string.
"""
import json
import logging
import time
from anthropic import Anthropic
from sqlalchemy.orm import Session
from app.config import settings
from app.models.workspace import Workspace
from app.models.ai import AIMessage
from app.services import agent_tools, agent_registry

logger = logging.getLogger(__name__)
client = Anthropic(api_key=settings.anthropic_api_key)

MAX_TOOL_ROUNDS = 10


def get_conversation_history(
    conversation_id: str, db: Session, limit: int = 20
) -> list[dict]:
    """Return the last N user/assistant messages in chronological order.
    Fetched newest-first then reversed so Claude sees the natural flow.
    """
    messages = (
        db.query(AIMessage)
        .filter(AIMessage.conversation_id == conversation_id)
        .order_by(AIMessage.created_at.desc())
        .limit(limit)
        .all()
    )
    return [{"role": m.role, "content": m.content} for m in reversed(messages)]


def chat(
    workspace_id: str,
    conversation_id: str,
    user_message: str,
    db: Session,
) -> str:
    """
    Agentic chat loop. Claude calls tools to query workspace data before answering.
    Loops until stop_reason == 'end_turn' or MAX_TOOL_ROUNDS is reached.
    If rounds are exhausted, _synthesis_pass() forces a final answer from accumulated results.
    """
    workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    tools = agent_registry.get_tools_for_vertical(workspace.vertical)
    history = get_conversation_history(conversation_id, db)

    system_prompt = (
        f"You are an investigation assistant for workspace '{workspace.name}'. "
        f"Subject: {workspace.subject_name or 'Not specified'}. "
        f"Vertical: {workspace.vertical}. "
        "Use the available tools to look up data before answering. "
        "Answer accurately from tool results only — do not speculate beyond what the data shows. "
        "Be precise with numbers, dates, names, and document references. "
        "Reference documents by filename, not by ID. "
        "When identifying something not yet investigated, end with: "
        "'Next lead to consider: [question]'."
    )

    messages = history + [{"role": "user", "content": user_message}]
    rounds = 0

    while rounds < MAX_TOOL_ROUNDS:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4096,
            system=system_prompt,
            tools=tools,
            messages=messages,
        )

        if response.stop_reason == "end_turn":
            return _extract_text(response)

        if response.stop_reason == "tool_use":
            messages.append({"role": "assistant", "content": response.content})
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    start = time.time()
                    result = agent_tools.execute(
                        block.name, workspace_id, db, block.input
                    )
                    elapsed = time.time() - start
                    logger.info(
                        "tool_call name=%s params=%s result_size=%d latency=%.3fs",
                        block.name,
                        block.input,
                        len(str(result)),
                        elapsed,
                    )
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(result),
                    })
            messages.append({"role": "user", "content": tool_results})
            rounds += 1
            continue

        break  # Unexpected stop reason — fall through to synthesis pass

    return _synthesis_pass(messages)


def _synthesis_pass(messages: list[dict]) -> str:
    """Force a final answer when the tool-use loop hits MAX_TOOL_ROUNDS.
    Sends accumulated messages to Claude with tools disabled and a directive to synthesize.
    """
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        system=(
            "You've gathered the following tool results. "
            "Provide your final answer to the user's question using only this data. "
            "No further tool calls are available."
        ),
        messages=messages,
    )
    return _extract_text(response)


def _extract_text(response) -> str:
    """Extract the first text block from a Claude response content list."""
    for block in response.content:
        if hasattr(block, "text"):
            return block.text
    return "I was unable to produce a response."
```

- [ ] **Step 4: Run test_ai.py to confirm updated tests pass**

```
cd backend
pytest tests/test_ai.py -v
```

Expected: all 3 PASS.

- [ ] **Step 5: Run full test suite to confirm nothing regressed**

```
cd backend
pytest tests/ -v
```

Expected: all tests PASS. If test_agent_tools.py fails due to import issues, ensure `backend/app/services/__init__.py` exists (it should — it's already in the repo).

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/ai_engine.py backend/tests/test_ai.py
git commit -m "feat: replace ai_engine.chat with native tool-use agentic loop"
```

---

## Task 8: Test the agentic loop with tool calls

**Files:**
- Modify: `backend/tests/test_ai.py`

These tests verify the multi-round loop mechanics — tool dispatch, synthesis pass, and max rounds cap — without hitting the real Claude API.

- [ ] **Step 1: Add loop mechanic tests**

Append to `backend/tests/test_ai.py`:

```python
from app.services.ai_engine import chat, _synthesis_pass, _extract_text
from app.models.workspace import Workspace
from app.models.ai import AIConversation
import uuid


@pytest.fixture
def ws_and_conv(db):
    ws = Workspace(id=str(uuid.uuid4()), name="Loop Test WS", vertical="fraud")
    db.add(ws)
    conv = AIConversation(id=str(uuid.uuid4()), workspace_id=ws.id)
    db.add(conv)
    db.commit()
    return ws, conv


def _mock_tool_use_then_end_turn(tool_name: str, tool_input: dict, final_text: str):
    """Return two side_effect responses: round 1 = tool_use, round 2 = end_turn."""
    # Round 1: Claude requests a tool call
    tool_block = MagicMock()
    tool_block.type = "tool_use"
    tool_block.id = "tool_abc123"
    tool_block.name = tool_name
    tool_block.input = tool_input

    round1 = MagicMock()
    round1.stop_reason = "tool_use"
    round1.content = [tool_block]

    # Round 2: Claude returns a final text answer
    text_block = MagicMock()
    text_block.type = "text"
    text_block.text = final_text
    text_block.id = None

    round2 = MagicMock()
    round2.stop_reason = "end_turn"
    round2.content = [text_block]

    return [round1, round2]


def test_chat_executes_tool_and_returns_final_answer(db, ws_and_conv):
    ws, conv = ws_and_conv
    side_effects = _mock_tool_use_then_end_turn(
        tool_name="get_findings",
        tool_input={},
        final_text="No findings recorded yet in this workspace.",
    )
    with patch("app.services.ai_engine.client") as mock_client:
        mock_client.messages.create.side_effect = side_effects
        result = chat(ws.id, conv.id, "What findings exist?", db)

    assert result == "No findings recorded yet in this workspace."
    assert mock_client.messages.create.call_count == 2


def test_chat_synthesis_pass_triggered_at_max_rounds(db, ws_and_conv):
    ws, conv = ws_and_conv

    # 10 tool_use rounds then 1 synthesis end_turn
    tool_block = MagicMock()
    tool_block.type = "tool_use"
    tool_block.id = "tool_xyz"
    tool_block.name = "get_findings"
    tool_block.input = {}

    tool_round = MagicMock()
    tool_round.stop_reason = "tool_use"
    tool_round.content = [tool_block]

    synthesis_text = MagicMock()
    synthesis_text.type = "text"
    synthesis_text.text = "Synthesized answer after max rounds."
    synthesis_text.id = None

    synthesis_round = MagicMock()
    synthesis_round.stop_reason = "end_turn"
    synthesis_round.content = [synthesis_text]

    side_effects = [tool_round] * 10 + [synthesis_round]

    with patch("app.services.ai_engine.client") as mock_client:
        mock_client.messages.create.side_effect = side_effects
        result = chat(ws.id, conv.id, "Run a deep analysis.", db)

    assert result == "Synthesized answer after max rounds."
    # 10 tool rounds + 1 synthesis call
    assert mock_client.messages.create.call_count == 11


def test_extract_text_returns_first_text_block():
    block = MagicMock()
    block.text = "Hello from Claude"
    response = MagicMock()
    response.content = [block]
    assert _extract_text(response) == "Hello from Claude"


def test_extract_text_fallback_when_no_text_block():
    block = MagicMock(spec=[])  # no 'text' attribute
    response = MagicMock()
    response.content = [block]
    assert _extract_text(response) == "I was unable to produce a response."
```

- [ ] **Step 2: Run tests to confirm they fail**

```
cd backend
pytest tests/test_ai.py::test_chat_executes_tool_and_returns_final_answer -v
```

Expected: FAIL — tests do not exist yet (before appending).

- [ ] **Step 3: Run new tests after adding them**

```
cd backend
pytest tests/test_ai.py -v
```

Expected: all tests PASS.

- [ ] **Step 4: Run full suite one final time**

```
cd backend
pytest tests/ -v
```

Expected: all tests PASS with no regressions.

- [ ] **Step 5: Commit**

```bash
git add backend/tests/test_ai.py
git commit -m "test: agentic loop mechanics — tool dispatch, synthesis pass, max rounds"
```

---

## Self-Review

**Spec coverage check:**

| Spec requirement | Covered by task |
|-----------------|-----------------|
| 6 read-only tools | Tasks 1–5 |
| execute() dispatcher with workspace_id injection | Task 1 |
| JSON schemas + vertical registry | Task 6 |
| Agentic loop (max 10 rounds) | Task 7 |
| Synthesis pass on max rounds | Task 7, Task 8 |
| Tool call logging (name, params, size, latency) | Task 7 |
| Tool result size limits (≤10 docs, ≤50 rows) | Tasks 1, 3, 4 |
| Workspace scoping on all tools | Tasks 1–5 |
| System prompt behavioral instructions | Task 7 |
| _extract_text fallback | Task 8 |
| Existing tests updated for new loop | Task 7–8 |

**Placeholder scan:** No TBDs. All code blocks are complete. ✓

**Type consistency:** `execute()` signature (`tool_name, workspace_id, db, params`) matches all call sites in `ai_engine.py`. `get_tools_for_vertical()` returns `list[dict]` which is what `client.messages.create(tools=...)` expects. ✓
