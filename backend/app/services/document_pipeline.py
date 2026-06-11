"""
Document ingestion pipeline — steps run in this exact order:
1.  Hash (evidence lock — must be first)
2.  Store file to disk
3.  OCR / text extraction
4.  Detect document type
5.  Match schema
6.  Extract fields (direct XML parse OR Claude extraction)
7.  Generate standardized filename
8.  Update FTS search index
9.  Audit log

Gap fixes applied:
- Gap 1: process_upload_background() runs after the HTTP response is sent.
- Gap 2: each step fails fast with extraction_status='failed'/'no_schema' + error logged.
- Gap 3: parse_strategy on the schema drives routing — 'xml_direct' uses direct XML parse, 'claude' uses Claude extraction.

WALKTHROUGH — two ideas hold this file together:

1. SYNC vs BACKGROUND split. Only steps 1–2 (hash + store) run while the user
   waits for the HTTP response — they're fast and must succeed before we promise
   the upload landed. Steps 3–9 (OCR, Claude, indexing) are slow and run AFTER
   the response is sent, in process_upload_background(). That's why there are two
   entry points and two DB sessions: the request's session is already closed by
   the time the background work runs.

2. FAIL-FAST, hash-first. The hash is computed before anything else (it's the
   evidence lock — see create_pending_document). After that, every slow step is
   wrapped in try/except that calls _fail() and returns. One broken step never
   cascades; the document just stops with a recorded reason. The exception is
   "non-fatal" steps (naming, embedding) that log a warning and continue — read
   on for which is which and why.
"""

import hashlib
import logging
import uuid
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.models.document import Document
from app.models.document_schema import DocumentSchema
from app.models.lead import InvestigationLead
from app.models.workspace import Workspace
from app.services import audit
from app.services.extraction_engine import (
    detect_document_type,
    extract_fields,
    get_schema_for_type,
    save_extractions,
)
from app.services.naming import generate_standardized_name
from app.services.ocr import extract_text
from app.services.xml_parser import is_valid_xml_bytes, parse_xml_document

logger = logging.getLogger(__name__)

EXTENSION_TO_TYPE = {
    ".pdf": "pdf",
    ".png": "image",
    ".jpg": "image",
    ".jpeg": "image",
    ".tiff": "image",
    ".tif": "image",
    ".csv": "csv",
    ".txt": "text",
    ".xml": "xml",
}


# ── Status helpers ──────────────────────────────────────────────────────────


def _fail(doc: Document, error: str, db: Session) -> None:
    """Mark a document as failed and clean up its stored file (L3)."""
    doc.extraction_status = "failed"
    doc.extraction_error = error[:500]
    db.commit()
    logger.error(f"Pipeline failed for doc {doc.id}: {error}")

    if doc.file_path:
        try:
            Path(doc.file_path).unlink(missing_ok=True)
        except Exception as e:
            logger.warning(f"File cleanup failed for doc {doc.id}: {e}")

    try:
        audit.log(
            db,
            action="upload_failed",
            user_id=doc.uploaded_by,
            workspace_id=doc.workspace_id,
            entity_type="document",
            entity_id=doc.id,
            after_state={"error": error[:500], "status": "failed"},
        )
    except Exception as e:
        logger.warning(f"Audit log failed for _fail on doc {doc.id}: {e}")


def _no_schema(doc: Document, doc_type: str, workspace_id: str, db: Session) -> None:
    """
    Mark a document as no_schema and create an investigation lead so the
    investigator knows to add a schema for this document type.
    """
    doc.extraction_status = "no_schema"
    doc.extraction_error = f"No active schema for document type '{doc_type}'"
    db.commit()

    # Auto-create a lead so the investigator can't miss it
    lead = InvestigationLead(
        workspace_id=workspace_id,
        question=(
            f"New document type detected: '{doc_type}' — "
            f"file '{doc.original_filename}' needs a schema before fields can be extracted. "
            f"Go to document_schemas and add a schema for this type."
        ),
        source="document_pipeline",
        originated_by="ai",
        status="pending",
    )
    db.add(lead)
    db.commit()

    logger.warning(
        f"No schema for doc_type='{doc_type}' | doc_id={doc.id} | "
        f"file='{doc.original_filename}' | workspace={workspace_id}. "
        "Investigation lead created."
    )


# ── Step 1–2: hash + store (synchronous, runs before response is sent) ──────


def find_existing_by_hash(workspace_id: str, sha256_hash: str, db: Session) -> Document | None:
    """Return a non-deleted document in this workspace with a matching hash, or None.
    The SHA-256 hash is the evidence lock — identical bytes are the same evidence."""
    return (
        db.query(Document)
        .filter(
            Document.workspace_id == workspace_id,
            Document.sha256_hash == sha256_hash,
            Document.is_deleted == False,  # noqa: E712
        )
        .first()
    )


def create_pending_document(
    filename: str,
    file_bytes: bytes,
    workspace_id: str,
    user_id: str,
    db: Session,
    source_type: str = "upload",
    source_ref: str | None = None,
) -> Document:
    """
    Compute the SHA-256 hash, store the file to disk, and create a pending
    Document record. Returns immediately — pipeline runs in the background.
    """
    # WALKTHROUGH: the hash is the FIRST thing that happens to a file, before it
    # touches disk, OCR, or Claude. Why first? It's the evidence lock — it
    # fingerprints the exact bytes that arrived. If hashing came after any step
    # that could alter the file, you could no longer prove what was uploaded.
    # find_existing_by_hash() uses this same value for dedup: identical bytes
    # are, by definition, the same piece of evidence.
    sha256_hash = hashlib.sha256(file_bytes).hexdigest()

    ext = Path(filename).suffix.lower()
    file_type = EXTENSION_TO_TYPE.get(ext, "other")

    upload_dir = Path(settings.upload_dir) / workspace_id
    upload_dir.mkdir(parents=True, exist_ok=True)
    stored_name = f"{uuid.uuid4()}{ext}"
    file_path = upload_dir / stored_name
    file_path.write_bytes(file_bytes)

    doc = Document(
        workspace_id=workspace_id,
        filename=filename,  # overwritten by standardized name in background
        original_filename=filename,
        file_path=str(file_path),
        file_type=file_type,
        sha256_hash=sha256_hash,
        source_type=source_type,
        source_ref=source_ref,
        size_bytes=len(file_bytes),
        extraction_status="pending",
        uploaded_by=user_id,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


# ── Background entry point ───────────────────────────────────────────────────


def process_upload_background(
    doc_id: str,
    file_bytes: bytes,
    original_filename: str,
    workspace_id: str,
    user_id: str,
) -> None:
    """
    Background task entry point. Creates its own DB session because the
    request session is closed before this runs (BackgroundTasks fire after
    the HTTP response is sent).
    """
    # WALKTHROUGH: this is the seam between "the user is waiting" and "the user
    # has their response and walked away." Everything below runs detached. Two
    # consequences drive the design: (1) we open our own SessionLocal() because
    # the request's session no longer exists; (2) there is no HTTP response left
    # to return an error to — so failures can only be RECORDED (on the document
    # row + audit log), never raised to a caller. The broad except below is the
    # last safety net: if anything escapes _run_pipeline, mark the doc failed
    # rather than let a background thread die silently.
    db = SessionLocal()
    try:
        _run_pipeline(doc_id, file_bytes, original_filename, workspace_id, user_id, db)
    except Exception as e:
        # Safety net — should not normally reach here
        logger.exception(f"Unhandled error in background pipeline for doc {doc_id}: {e}")
        try:
            doc = db.query(Document).filter(Document.id == doc_id).first()
            if doc:
                _fail(doc, f"Unhandled pipeline error: {e}", db)
        except Exception:
            pass
    finally:
        db.close()


# ── Main pipeline ────────────────────────────────────────────────────────────


def _run_pipeline(
    doc_id: str,
    file_bytes: bytes,
    original_filename: str,
    workspace_id: str,
    user_id: str,
    db: Session,
) -> None:
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        logger.error(f"Pipeline: document {doc_id} not found in database")
        return

    ext = Path(original_filename).suffix.lower()
    file_type = EXTENSION_TO_TYPE.get(ext, "other")

    # ── Step 3: OCR ─────────────────────────────────────────────────────────
    # WALKTHROUGH: this try/except/_fail()/return shape repeats for every slow
    # step below. Read it once here: a step that can't complete marks the doc
    # 'failed' with the reason, then RETURNS — it does not raise and does not
    # fall through. That's the fail-fast spine. Each step assumes the previous
    # ones succeeded, so stopping at the first failure keeps later steps from
    # running on garbage (e.g. detecting a type from empty OCR text).
    try:
        ocr_text = extract_text(file_bytes, file_type)
    except Exception as e:
        _fail(doc, f"OCR failed: {e}", db)
        return

    # ── Step 4: Detect document type ────────────────────────────────────────
    try:
        doc_type = detect_document_type(ocr_text, db)
    except Exception as e:
        _fail(doc, f"Type detection failed: {e}", db)
        return

    doc.detected_doc_type = doc_type
    db.commit()

    # ── Step 5: Match schema ────────────────────────────────────────────────
    # Look up the workspace vertical so the schema registry can prefer
    # vertical-specific schemas over general ones when both exist.
    workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    workspace_vertical = workspace.vertical if workspace else "general"

    schema: DocumentSchema | None = get_schema_for_type(doc_type, db, workspace_vertical)

    if not schema:
        # WALKTHROUGH: "no schema" is NOT a failure — it's a known-but-unhandled
        # document type. So instead of _fail(), we take a softer branch: mark the
        # doc 'no_schema', auto-create an investigation lead (see _no_schema) so a
        # human is told to add the schema, and STILL index the raw OCR text so the
        # document is searchable in the meantime. Then we return early — there are
        # no fields to extract without a schema. Note it still writes an audit row:
        # every terminal state, success or not, leaves a trail.
        _no_schema(doc, doc_type, workspace_id, db)
        # Still index the OCR text so the document is searchable
        _update_search_index(doc, ocr_text, [], db)
        _write_audit(doc, user_id, workspace_id, db)
        return

    doc.schema_id = schema.id
    db.commit()

    # ── Step 6: Extract fields ──────────────────────────────────────────────
    # Both paths return list[dict] with field_name/field_value/field_type/confidence.
    # save_extractions() writes them to document_extractions for both paths.
    #
    # WALKTHROUGH: this is the routing fork (Gap 3). The SCHEMA decides how its
    # own fields get extracted, not the pipeline. 'xml_direct' means the source
    # is structured XML we can parse deterministically — no AI, confidence is a
    # flat 1.0 because there's nothing to be uncertain about. Everything else
    # goes through Claude. Both branches return the SAME shape, which is the
    # whole point: save_extractions() and the indexer below don't care which
    # path produced the rows. A new strategy = a new branch here, nothing
    # downstream changes.
    raw_extractions: list[dict] = []
    try:
        if schema.parse_strategy == "xml_direct" and is_valid_xml_bytes(file_bytes):
            # XML direct parse — no Claude, confidence = 1.0
            raw_extractions = parse_xml_document(file_bytes, schema)
        else:
            # Claude extraction
            raw_extractions = extract_fields(ocr_text, schema, doc.id, workspace_id)

        save_extractions(raw_extractions, doc.id, workspace_id, schema.id, db)
    except Exception as e:
        _fail(doc, f"Extraction failed: {e}", db)
        return

    # ── Step 6a: Field validation ────────────────────────────────────────────
    if schema.parse_strategy == "claude" and schema.schema_fields:
        try:
            from app.services.field_validator import validate_extractions

            validation_errors = validate_extractions(raw_extractions, schema.schema_fields)
            if validation_errors:
                required_failures = [e for e in validation_errors if e.rule == "required"]
                for err in validation_errors:
                    logger.warning(f"Validation error in doc {doc.id}: {err.message}")
                if required_failures:
                    doc.extraction_status = "needs_review"
                    doc.extraction_error = "; ".join(e.message for e in required_failures[:3])
                    db.commit()
        except Exception as e:
            logger.warning(f"Field validation failed for doc {doc.id}: {e}")

    # C2 guard: a claude schema with defined fields that yielded zero rows is a failure,
    # not a silent complete. (extract_fields raises if all batches failed; this catches
    # the rare case where batches succeed but Claude returns no extractions.)
    if schema.parse_strategy == "claude" and schema.schema_fields and not raw_extractions:
        _fail(doc, "Extraction returned zero fields — possible API outage or empty response", db)
        return

    # ── Step 6b: Evaluate confidence + retry low-confidence fields (claude only) ──
    # XML direct always produces confidence=1.0 — skip evaluator entirely.
    #
    # WALKTHROUGH: this is a self-correction loop, and it's the most subtle part
    # of the file. Read it as: evaluate → maybe retry → re-evaluate.
    #   1. evaluate() flags fields below their confidence threshold (per-field
    #      thresholds override the schema default; AI confidence and OCR
    #      confidence are checked separately).
    #   2. If any are low, run_retry() re-asks Claude for ONLY those fields.
    #   3. We evaluate AGAIN on the retry results. If fields are STILL low, the
    #      doc is marked 'needs_review' — a human has to look. We don't loop
    #      forever; one retry, then escalate to a person.
    # The whole block is best-effort: wrapped in try/except that only logs, so a
    # crash in the evaluator never fails an otherwise-good extraction. Contrast
    # with Step 6 above, where a failure IS fatal — the difference is whether the
    # step produces the core data (fatal) or just grades it (best-effort).
    if schema.parse_strategy == "claude":
        try:
            from app.services.extraction_evaluator import evaluate, run_retry

            _field_ai_thresholds = {
                f["name"]: f["ai_threshold"]
                for f in (schema.schema_fields or [])
                if "ai_threshold" in f
            }
            _field_ocr_thresholds = {
                f["name"]: f["ocr_threshold"]
                for f in (schema.schema_fields or [])
                if "ocr_threshold" in f
            }
            eval_result = evaluate(
                raw_extractions,
                schema.default_confidence_threshold,
                field_thresholds=_field_ai_thresholds or None,
                ocr_threshold=schema.default_confidence_threshold,
                ocr_field_thresholds=_field_ocr_thresholds or None,
            )
            if eval_result.needs_review:
                logger.info(
                    f"Evaluator: {len(eval_result.low_confidence_fields)} low-confidence fields "
                    f"in doc {doc.id} — retrying"
                )
                retry_extractions = run_retry(
                    document_id=doc.id,
                    workspace_id=workspace_id,
                    ocr_text=ocr_text,
                    schema=schema,
                    low_confidence_field_names=eval_result.low_confidence_fields,
                    db=db,
                )
                if retry_extractions:
                    final_eval = evaluate(
                        retry_extractions,
                        schema.default_confidence_threshold,
                        field_thresholds=_field_ai_thresholds or None,
                        ocr_threshold=schema.default_confidence_threshold,
                        ocr_field_thresholds=_field_ocr_thresholds or None,
                    )
                    if final_eval.needs_review:
                        doc.extraction_status = "needs_review"
                        db.commit()
                        logger.info(
                            f"Doc {doc.id} flagged needs_review: "
                            f"{len(final_eval.low_confidence_fields)} fields still below threshold"
                        )
                else:
                    doc.extraction_status = "needs_review"
                    db.commit()
        except Exception as e:
            logger.warning(f"Extraction evaluator failed for doc {doc.id}: {e}")

    # ── Step 7: Standardized filename ───────────────────────────────────────
    # WALKTHROUGH: here's the "non-fatal" pattern promised in the module docstring.
    # Naming, FTS indexing (Step 8), and embedding (Step 8.5) all catch their own
    # exceptions, log a warning, and CONTINUE — they never call _fail(). Why?
    # Because by this point the evidence (hash) and the extracted data already
    # exist and are saved. A document with its original filename and no embedding
    # is still a complete, queryable record; losing a pretty filename is not worth
    # discarding the extraction. The dividing line throughout this file: anything
    # upstream of saved extractions fails the doc; anything that only enhances an
    # already-saved doc degrades gracefully.
    try:
        standardized = generate_standardized_name(
            ocr_text, original_filename, ext.lstrip(".") or "pdf", db
        )
        doc.filename = standardized
    except Exception as e:
        # Naming failure is non-fatal — keep original filename
        logger.warning(f"naming failed for doc {doc.id}: {e} — keeping original filename")
        pass

    # ── Step 8: Update FTS search index ─────────────────────────────────────
    # raw_extractions is always list[dict] — no type branching needed
    extra_text = " ".join(
        f"{e.get('field_name', '')} {e.get('field_value', '')}"
        for e in raw_extractions
        if e.get("field_value")
    )
    _update_search_index(doc, ocr_text, extra_text, db)

    if doc.extraction_status == "pending":
        doc.extraction_status = "complete"
    db.commit()

    # ── Step 8.5: Generate embedding for semantic search ─────────────────────
    try:
        from app.services import embedding_service

        embedding_service.embed_document(doc.id, workspace_id, db)
    except Exception:
        logger.warning("Embedding failed for document %s — continuing", doc.id)

    # ── Step 9: Audit log ────────────────────────────────────────────────────
    _write_audit(doc, user_id, workspace_id, db)

    logger.info(
        f"Pipeline complete: doc={doc.id} type={doc_type} "
        f"fields={len(raw_extractions)} file='{original_filename}'"
    )


def _update_search_index(
    doc: Document,
    ocr_text: str,
    extra_text: str | list,
    db: Session,
) -> None:
    if isinstance(extra_text, list):
        extra_text = " ".join(extra_text)
    combined = f"{ocr_text} {extra_text}".strip()
    try:
        db.execute(
            text(
                "UPDATE documents SET search_vector = to_tsvector('english', :content), "
                "ocr_text = :ocr WHERE id = :doc_id"
            ),
            {"content": combined[:1_000_000], "ocr": ocr_text[:500_000], "doc_id": doc.id},
        )
        db.commit()
    except Exception as e:
        logger.warning(f"FTS index update failed for doc {doc.id}: {e}")


def _write_audit(doc: Document, user_id: str, workspace_id: str, db: Session) -> None:
    try:
        audit.log(
            db,
            action="uploaded",
            user_id=user_id,
            workspace_id=workspace_id,
            entity_type="document",
            entity_id=doc.id,
            after_state={
                "filename": doc.filename,
                "hash": doc.sha256_hash,
                "doc_type": doc.detected_doc_type,
                "status": doc.extraction_status,
            },
        )
    except Exception as e:
        logger.warning(f"Audit log failed for doc {doc.id}: {e}")
