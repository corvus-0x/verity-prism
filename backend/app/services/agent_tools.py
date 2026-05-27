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
    """Look up entities by name (case-insensitive partial match). Returns full data for one match,
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


_VALID_TRANSACTION_TYPES = {
    "purchase", "transfer", "lien", "loan", "donation", "construction", "compensation"
}


def get_transactions(
    workspace_id: str,
    db: Session,
    min_amount: float = None,
    max_amount: float = None,
    transaction_type: str = None,
) -> dict:
    """Filter transactions by amount range and/or type.
    Returns up to 50 matching records with overpay percentage calculated.
    Invalid transaction_type values return an empty result rather than raising a DB error,
    because PostgreSQL enums reject unknown values at query time.
    """
    q = db.query(Transaction).filter(Transaction.workspace_id == workspace_id)
    if transaction_type:
        if transaction_type not in _VALID_TRANSACTION_TYPES:
            return {"transactions": [], "count": 0}
        q = q.filter(Transaction.transaction_type == transaction_type)
    if min_amount is not None:
        q = q.filter(Transaction.amount_paid >= min_amount)
    if max_amount is not None:
        q = q.filter(Transaction.amount_paid <= max_amount)

    rows = q.limit(50).all()
    results = []
    for t in rows:
        overpay_pct = None
        if t.amount_paid is not None and t.appraised_value is not None and float(t.appraised_value) > 0:
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
            "amount_paid": str(t.amount_paid) if t.amount_paid is not None else None,
            "appraised_value": str(t.appraised_value) if t.appraised_value is not None else None,
            "overpay_pct": overpay_pct,
            "transaction_date": str(t.transaction_date) if t.transaction_date else None,
            "instrument_number": t.instrument_number,
            "notes": t.notes,
        })
    return {"transactions": results, "count": len(results)}


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
                "source": lead.originated_by,
            }
            for lead in leads
        ],
        "count": len(leads),
    }


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
