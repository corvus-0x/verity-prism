"""
NLP Search Service — translates plain-English queries into PostgreSQL FTS
+ field-level filters on document_extractions.

How it works:
1. get_known_field_names() tells Claude which fields exist in this workspace
2. translate_query() asks Claude to produce structured filters from the query
3. run_search() executes FTS + field filters and returns matching documents
"""
import json
import logging

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.document_extraction import DocumentExtraction
from app.services import claude_client
from app.utils.json_helpers import strip_json_fences

logger = logging.getLogger(__name__)


def get_known_field_names(workspace_id: str, db: Session) -> list[str]:
    """
    Return the distinct field names extracted in this workspace.
    Passed to Claude so it knows which fields are available to filter on.
    """
    results = (
        db.query(DocumentExtraction.field_name)
        .filter(DocumentExtraction.workspace_id == workspace_id)
        .distinct()
        .all()
    )
    return [r[0] for r in results]


def translate_query(natural_language_query: str, field_names: list[str]) -> dict:
    """
    Ask Claude to translate a plain-English query into structured filters.

    Returns a dict with:
    - fts_query: keyword string for full-text search (empty string = no FTS)
    - field_filters: list of {field_name, operator, value} dicts
    - doc_type_filter: a document type string or null
    """
    fields_context = ", ".join(field_names) if field_names else "no fields extracted yet"

    prompt = f"""You translate plain English document search queries into structured database filters.

Available extracted field names in this workspace: {fields_context}

For the query below, return JSON with:
- "fts_query": keywords to search in full document text (string, can be "")
- "field_filters": list of field-level filters, each with:
    - "field_name": one of the available field names above
    - "operator": "eq" (equals), "contains" (text contains), "gt" (greater than), "lt" (less than)
    - "value": the value to compare against (always a string)
- "doc_type_filter": a specific document type to filter by (or null for all types)

Query: "{natural_language_query}"

Respond with JSON only. Example:
{{
    "fts_query": "grantor name",
    "field_filters": [{{"field_name": "consideration_amount", "operator": "gt", "value": "100000"}}],
    "doc_type_filter": "DEED"
}}"""

    try:
        response = claude_client.get_client().messages.create(
            model="claude-sonnet-4-6",
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}]
        )
        return json.loads(strip_json_fences(response.content[0].text))
    except Exception as e:
        logger.warning(f"Query translation failed: {e} — falling back to FTS only")
        return {"fts_query": natural_language_query, "field_filters": [], "doc_type_filter": None}


def run_search(workspace_id: str, query_plan: dict, db: Session) -> list[dict]:
    """
    Execute the search against PostgreSQL.
    Combines FTS on documents.search_vector with field-level filters on
    document_extractions. Returns up to 50 matching documents with their
    extracted field values.
    """
    fts_query = query_plan.get("fts_query", "")
    field_filters = query_plan.get("field_filters", [])
    doc_type_filter = query_plan.get("doc_type_filter")

    # Base query — active documents in this workspace
    doc_query = db.query(Document).filter(
        Document.workspace_id == workspace_id,
        Document.is_deleted == False,  # noqa: E712
    )

    # Full-text search across OCR text and extracted field values
    if fts_query:
        doc_query = doc_query.filter(
            text("search_vector @@ plainto_tsquery('english', :query)").bindparams(
                query=fts_query
            )
        )

    # Document type filter
    if doc_type_filter:
        doc_query = doc_query.filter(Document.detected_doc_type == doc_type_filter)

    matching_docs = doc_query.limit(50).all()

    # Field-level filters — intersect doc IDs across all filters (AND logic)
    if field_filters:
        filtered_doc_ids: set[str] = set()
        first_filter = True

        for f in field_filters:
            extraction_query = db.query(DocumentExtraction.document_id).filter(
                DocumentExtraction.workspace_id == workspace_id,
                DocumentExtraction.field_name == f["field_name"],
                DocumentExtraction.field_value.isnot(None),
            )
            op = f.get("operator", "eq")
            val = f.get("value", "")

            if op == "eq":
                extraction_query = extraction_query.filter(
                    DocumentExtraction.field_value == val
                )
            elif op == "contains":
                extraction_query = extraction_query.filter(
                    DocumentExtraction.field_value.ilike(f"%{val}%")
                )
            elif op in ("gt", "lt"):
                # Guard against non-numeric field_value before CAST to avoid errors
                numeric_guard = text(
                    "field_value ~ '^[0-9]+(\\.[0-9]+)?$'"
                )
                comparator = ">" if op == "gt" else "<"
                extraction_query = extraction_query.filter(
                    numeric_guard,
                    text(f"CAST(field_value AS NUMERIC) {comparator} :val").bindparams(
                        val=float(val)
                    ),
                )

            ids = {r[0] for r in extraction_query.all()}
            if first_filter:
                filtered_doc_ids = ids
                first_filter = False
            else:
                filtered_doc_ids &= ids  # AND — must match all filters

        # Filter or expand matching docs based on field filter results
        matching_docs = [d for d in matching_docs if d.id in filtered_doc_ids]
        if not matching_docs and filtered_doc_ids:
            # FTS returned nothing but field filters matched — fetch those docs directly
            matching_docs = (
                db.query(Document)
                .filter(
                    Document.id.in_(filtered_doc_ids),
                    Document.is_deleted == False,  # noqa: E712
                )
                .limit(50)
                .all()
            )

    # Build result objects — include all extracted fields for context
    results = []
    for doc in matching_docs:
        extractions = (
            db.query(DocumentExtraction)
            .filter(DocumentExtraction.document_id == doc.id)
            .all()
        )
        matched_fields = {e.field_name: e.field_value for e in extractions}

        results.append({
            "document_id": doc.id,
            "filename": doc.filename,
            "original_filename": doc.original_filename,
            "detected_doc_type": doc.detected_doc_type,
            "extraction_status": doc.extraction_status,
            "uploaded_at": doc.uploaded_at.isoformat(),
            "matched_fields": matched_fields,
        })

    return results
