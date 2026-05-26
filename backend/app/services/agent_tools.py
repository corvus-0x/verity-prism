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
    FTS query uses PostgreSQL plainto_tsquery against the search_vector column,
    which is populated by the extraction pipeline after each document is processed.
    """
    q = db.query(Document).filter(
        Document.workspace_id == workspace_id,
        Document.is_deleted == False,
    )
    if query:
        q = q.filter(
            Document.search_vector.op("@@")(
                sql_text("plainto_tsquery('english', :query)").bindparams(query=query)
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
    This prevents prompt injection attacks where Claude could be tricked into
    querying data from a different workspace.
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
