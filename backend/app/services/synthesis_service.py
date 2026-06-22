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
from app.models.document_schema import DocumentSchema
from app.models.workspace import Workspace
from app.services import audit, claude_client, signal_registry
from app.services.claude_client import CHAT_MODEL
from app.services.export_service import latest_extractions
from app.services.saliences import DocumentMeta, Evidence, Salience, compute_saliences
from app.utils.json_helpers import strip_json_fences

logger = logging.getLogger(__name__)


class SynthesisError(Exception):
    """Domain error carrying the HTTP status the router should surface.
    Raised when synthesis cannot produce a usable brief (e.g. an unparseable
    model response) so the caller fails loudly instead of storing an empty brief."""

    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


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


def _log_synthesis_call(
    workspace_id: str,
    latency_ms: int,
    prompt_chars: int,
    response=None,
    error_message: str | None = None,
) -> None:
    """Write one brief_synthesis row to claude_call_logs. Opens its own session so
    logging never corrupts the request transaction; swallows all exceptions.
    """
    try:
        from app.database import SessionLocal
        from app.models.claude_call_log import ClaudeCallLog

        db = SessionLocal()
        try:
            usage = getattr(response, "usage", None)
            content = getattr(response, "content", None)
            row = ClaudeCallLog(
                call_type="brief_synthesis",
                workspace_id=workspace_id,
                model=CHAT_MODEL,
                success=response is not None,
                latency_ms=latency_ms,
                input_tokens=getattr(usage, "input_tokens", None),
                output_tokens=getattr(usage, "output_tokens", None),
                prompt_chars=prompt_chars,
                response_chars=len(content[0].text) if content else None,
                error_message=error_message,
            )
            db.add(row)
            db.commit()
        finally:
            db.close()
    except Exception as e:
        logger.warning(f"claude_call_log write failed: {e}")


def _validate_and_annotate(brief: dict, evidence: list[Evidence]) -> dict:
    """Drop claims that cite no valid evidence id, strip unknown ids from the
    rest, annotate each surviving claim with grounding_confidence = the minimum
    confidence of its cited rows, and report how many claims were dropped (an
    invalid-citation / hallucination signal).
    """
    by_id = {e.id: e for e in evidence}
    claims = []
    dropped = 0
    for claim in brief.get("claims", []) or []:
        sources = [s for s in (claim.get("sources") or []) if s in by_id]
        if not sources:
            dropped += 1  # unfalsifiable — a claim with no real citation is dropped
            continue
        claim["sources"] = sources
        claim["grounding_confidence"] = round(min(by_id[s].confidence for s in sources), 4)
        claims.append(claim)
    if dropped:
        logger.warning("Brief synthesis dropped %d claim(s) with invalid citations", dropped)
    return {
        "summary": brief.get("summary", "") or "",
        "claims": claims,
        "claims_dropped": dropped,
    }


def _required_fields_by_doc(docs: list[Document], db: Session) -> dict[str, set]:
    """Map each document id to the set of field names its schema marks as required.
    Used to score brief completeness against what each document was expected to yield."""
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
    """Read the workspace's non-deleted documents and their LATEST-attempt
    extraction rows into the citable evidence set + document metadata +
    required-field map. Reads only the universal IDP table (document_extractions,
    deduped to the highest attempt per field) plus document/schema metadata —
    no transactions/entities/findings, which are cap-flavored.
    """
    docs = (
        db.query(Document)
        .filter(Document.workspace_id == workspace_id, Document.is_deleted == False)  # noqa: E712
        .all()
    )
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
    evidence = []
    for d in docs:
        for r in latest_extractions(d.id, db):
            evidence.append(
                Evidence(
                    id=r.id,
                    document_id=r.document_id,
                    filename=d.filename,
                    doc_type=d.detected_doc_type,
                    field_name=r.field_name,
                    field_value=r.field_value,
                    field_type=r.field_type or "text",
                    confidence=r.confidence,
                    ocr_confidence=r.ocr_confidence,
                )
            )
    return evidence, documents, _required_fields_by_doc(docs, db)


def _synthesize(
    evidence: list[Evidence], saliences: list[Salience], workspace_id: str
) -> tuple[dict, dict]:
    """One constrained Claude call. Logs a brief_synthesis row, returns
    (parsed_brief, meta) with latency_ms. Degrades to an empty brief (never
    raises) only on unparseable JSON; a transport error is logged and re-raised.
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
    user_content = json.dumps(payload)
    prompt_chars = len(_SYNTHESIS_SYSTEM) + len(user_content)

    start = time.perf_counter()
    try:
        response = claude_client.get_client().messages.create(
            model=CHAT_MODEL,
            max_tokens=2048,
            system=_SYNTHESIS_SYSTEM,
            messages=[{"role": "user", "content": user_content}],
        )
    except Exception as e:
        latency_ms = int((time.perf_counter() - start) * 1000)
        _log_synthesis_call(workspace_id, latency_ms, prompt_chars, error_message=str(e))
        raise
    latency_ms = int((time.perf_counter() - start) * 1000)
    _log_synthesis_call(workspace_id, latency_ms, prompt_chars, response=response)

    usage = getattr(response, "usage", None)
    meta = {
        "model": CHAT_MODEL,
        "input_tokens": getattr(usage, "input_tokens", None),
        "output_tokens": getattr(usage, "output_tokens", None),
        "latency_ms": latency_ms,
    }
    try:
        parsed = json.loads(strip_json_fences(response.content[0].text))
    except Exception as e:
        logger.warning(f"Brief synthesis returned unparseable JSON: {e}")
        raise SynthesisError(502, "Brief synthesis returned an unparseable response") from e
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

    raw, meta = _synthesize(evidence, saliences, workspace_id)

    brief = _validate_and_annotate(raw, evidence)
    brief.update(meta)
    return brief


def resolve_citation(workspace_id: str, extraction_id: str, db: Session) -> dict | None:
    """Resolve one citation (extraction id) to its source detail, scoped to the
    workspace. Returns None if the id is not an extraction in this workspace.
    Reads only document_extractions + document metadata.
    """
    from app.models.document_extraction import DocumentExtraction

    row = (
        db.query(DocumentExtraction, Document.filename, Document.detected_doc_type)
        .join(Document, Document.id == DocumentExtraction.document_id)
        .filter(
            DocumentExtraction.id == extraction_id,
            DocumentExtraction.workspace_id == workspace_id,
            Document.workspace_id == workspace_id,
            Document.is_deleted == False,  # noqa: E712
        )
        .first()
    )
    if not row:
        return None
    ext = row.DocumentExtraction
    return {
        "extraction_id": ext.id,
        "document_id": ext.document_id,
        "filename": row.filename,
        "doc_type": row.detected_doc_type,
        "field_name": ext.field_name,
        "field_value": ext.field_value,
        "confidence": ext.confidence,
        "evidence": ext.evidence,
    }


def store_brief(workspace_id: str, brief: dict, db: Session, commit: bool = True) -> Brief:
    """Persist a brief as the next version for the workspace; prior versions are
    retained. Returns the stored row.

    Pass commit=False to flush only, so the caller can commit the brief together
    with its audit entry in one transaction (see generate_brief).
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
    db.flush()
    if commit:
        db.commit()
    db.refresh(row)
    return row


def generate_brief(workspace_id: str, user_id: str, db: Session) -> Brief:
    """Synthesize a brief, persist it as the next version, and audit it.
    Returns the stored row."""
    brief = synthesize_brief(workspace_id, db)
    row = store_brief(workspace_id, brief, db, commit=False)
    audit.log(
        db,
        action="brief_generated",
        user_id=user_id,
        workspace_id=workspace_id,
        entity_type="brief",
        entity_id=row.id,
        after_state={
            "version": row.version,
            "claim_count": len(row.claims),
            "claims_dropped": brief.get("claims_dropped", 0),
        },
    )
    return row


def get_latest_brief(workspace_id: str, db: Session) -> Brief | None:
    """Return the newest active brief for a workspace, or None if none exist."""
    return (
        db.query(Brief)
        .filter(Brief.workspace_id == workspace_id, Brief.is_deleted == False)  # noqa: E712
        .order_by(Brief.version.desc())
        .first()
    )


def list_briefs(workspace_id: str, db: Session) -> list[Brief]:
    """Return all active briefs for a workspace, newest version first."""
    return (
        db.query(Brief)
        .filter(Brief.workspace_id == workspace_id, Brief.is_deleted == False)  # noqa: E712
        .order_by(Brief.version.desc())
        .all()
    )
