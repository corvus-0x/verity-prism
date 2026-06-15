"""
Synthesis service — the engine's post-extraction intelligence layer.

Turns a workspace's document_extractions into a grounded brief: a summary
plus structured claims, each citing the extraction rows it came from.
Commodity extractors stop at fields; this reads across documents.

Pipeline: _assemble_evidence (DB read + universal saliences) -> _synthesize
(one constrained Claude call that may cite only supplied evidence ids) ->
_validate_and_annotate (drop fabricated citations, attach grounding
confidence from the cited rows).
"""

import json
import logging
import time

from sqlalchemy.orm import Session

from app.models.brief import Brief
from app.models.document import Document
from app.models.document_extraction import DocumentExtraction
from app.models.document_schema import DocumentSchema
from app.models.workspace import Workspace
from app.services import claude_client, signal_registry
from app.services.claude_client import CHAT_MODEL
from app.services.saliences import DocumentMeta, Evidence, Salience, compute_saliences
from app.utils.json_helpers import strip_json_fences

logger = logging.getLogger(__name__)

_SYNTHESIS_SYSTEM = (
    "You are the synthesis layer of a document-intelligence platform. You receive "
    "EVIDENCE (extracted fields, each with an id) and SALIENCES (notable "
    "cross-document facts already computed for you). Write a brief for an operator: "
    "a short summary plus a list of claims. EVERY claim MUST cite one or more "
    'evidence ids in its "sources" array, and you may cite ONLY ids that appear in '
    "the evidence. Never assert anything the evidence does not support. If nothing is "
    "notable, say so plainly and return few or no claims. Respond with JSON only: "
    '{"summary": "...", "claims": [{"text": "...", "sources": ["<evidence_id>"], '
    '"signal_type": "<salience type or general>"}]}'
)


def _validate_and_annotate(brief: dict, evidence: list[Evidence]) -> dict:
    """Drop claims that cite no valid evidence id, strip unknown ids from the
    rest, and annotate each surviving claim with grounding_confidence = the
    minimum confidence of its cited rows (so the brief can hedge weak claims).
    """
    by_id = {e.id: e for e in evidence}
    claims = []
    for claim in brief.get("claims", []) or []:
        sources = [s for s in (claim.get("sources") or []) if s in by_id]
        if not sources:
            continue  # unfalsifiable — a claim with no real citation is dropped
        claim["sources"] = sources
        claim["grounding_confidence"] = round(min(by_id[s].confidence for s in sources), 4)
        claims.append(claim)
    return {"summary": brief.get("summary", "") or "", "claims": claims}


def _required_fields_by_doc(docs: list[Document], db: Session) -> dict[str, set]:
    schema_ids = {d.schema_id for d in docs if d.schema_id}
    if not schema_ids:
        return {}
    schemas = {
        s.id: s for s in db.query(DocumentSchema).filter(DocumentSchema.id.in_(schema_ids)).all()
    }
    out: dict[str, set] = {}
    for d in docs:
        schema = schemas.get(d.schema_id)
        if not schema:
            continue
        required = {
            f.get("name")
            for f in (schema.schema_fields or [])
            if f.get("required") and f.get("name")
        }
        if required:
            out[d.id] = required
    return out


def _assemble_evidence(workspace_id: str, db: Session):
    """Read the workspace's non-deleted documents and their extraction rows into
    the citable evidence set + document metadata + required-field map. Reads only
    the universal IDP table (document_extractions) plus document/schema metadata —
    no transactions/entities/findings, which are cap-flavored.
    """
    docs = (
        db.query(Document)
        .filter(Document.workspace_id == workspace_id, Document.is_deleted == False)  # noqa: E712
        .all()
    )
    doc_by_id = {d.id: d for d in docs}
    documents = [
        DocumentMeta(
            id=d.id,
            filename=d.filename,
            doc_type=d.detected_doc_type,
            sha256_hash=d.sha256_hash,
            uploaded_at=d.uploaded_at.isoformat() if d.uploaded_at else None,
        )
        for d in docs
    ]
    rows = (
        db.query(DocumentExtraction).filter(DocumentExtraction.workspace_id == workspace_id).all()
    )
    evidence = [
        Evidence(
            id=r.id,
            document_id=r.document_id,
            filename=doc_by_id[r.document_id].filename,
            doc_type=doc_by_id[r.document_id].detected_doc_type,
            field_name=r.field_name,
            field_value=r.field_value,
            field_type=r.field_type or "text",
            confidence=r.confidence,
            ocr_confidence=r.ocr_confidence,
        )
        for r in rows
        if r.document_id in doc_by_id  # skip rows whose document is soft-deleted
    ]
    return evidence, documents, _required_fields_by_doc(docs, db)


def _synthesize(evidence: list[Evidence], saliences: list[Salience]) -> tuple[dict, dict]:
    """One constrained Claude call. Returns (parsed_brief, meta). Degrades to an
    empty brief (never raises) if Claude returns unparseable JSON.
    """
    payload = {
        "evidence": [
            {
                "id": e.id,
                "document": e.filename,
                "doc_type": e.doc_type,
                "field": e.field_name,
                "value": e.field_value,
            }
            for e in evidence
        ],
        "saliences": [{"type": s.type, "fact": s.description} for s in saliences],
    }
    response = claude_client.get_client().messages.create(
        model=CHAT_MODEL,
        max_tokens=2048,
        system=_SYNTHESIS_SYSTEM,
        messages=[{"role": "user", "content": json.dumps(payload)}],
    )
    usage = getattr(response, "usage", None)
    meta = {
        "model": CHAT_MODEL,
        "input_tokens": getattr(usage, "input_tokens", None),
        "output_tokens": getattr(usage, "output_tokens", None),
    }
    try:
        parsed = json.loads(strip_json_fences(response.content[0].text))
    except Exception as e:
        logger.warning(f"Brief synthesis returned unparseable JSON: {e}")
        parsed = {"summary": "", "claims": []}
    return parsed, meta


def synthesize_brief(workspace_id: str, db: Session) -> dict:
    """Generate a brief dict (summary, claims, model/usage/latency meta) for a
    workspace. No persistence — the eval harness and the router both call this.
    """
    workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    vertical = getattr(workspace, "vertical", None) if workspace else None

    evidence, documents, required_by_doc = _assemble_evidence(workspace_id, db)
    saliences = compute_saliences(
        evidence, documents, required_by_doc, signal_registry.get_detectors(vertical)
    )

    start = time.perf_counter()
    raw, meta = _synthesize(evidence, saliences)
    meta["latency_ms"] = int((time.perf_counter() - start) * 1000)

    brief = _validate_and_annotate(raw, evidence)
    brief.update(meta)
    return brief


def store_brief(workspace_id: str, brief: dict, db: Session) -> Brief:
    """Persist a brief as the next version for the workspace; prior versions are
    retained. Returns the stored row.
    """
    last = (
        db.query(Brief)
        .filter(Brief.workspace_id == workspace_id, Brief.is_deleted == False)  # noqa: E712
        .order_by(Brief.version.desc())
        .first()
    )
    row = Brief(
        workspace_id=workspace_id,
        version=(last.version + 1) if last else 1,
        summary=brief.get("summary", ""),
        claims=brief.get("claims", []),
        model=brief.get("model"),
        latency_ms=brief.get("latency_ms"),
        input_tokens=brief.get("input_tokens"),
        output_tokens=brief.get("output_tokens"),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row
