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
"""

import hashlib
import logging
import uuid
from pathlib import Path

from sqlalchemy.orm import Session
from sqlalchemy import text

from app.config import settings
from app.database import SessionLocal
from app.models.document import Document
from app.models.lead import InvestigationLead
from app.models.document_schema import DocumentSchema
from app.models.workspace import Workspace
from app.services.ocr import extract_text
from app.services.extraction_engine import (
    detect_document_type,
    get_schema_for_type,
    extract_fields,
    save_extractions,
)
from app.services.xml_parser import is_valid_xml_bytes, parse_xml_document
from app.services.naming import generate_standardized_name
from app.services import audit

logger = logging.getLogger(__name__)

EXTENSION_TO_TYPE = {
    ".pdf": "pdf", ".png": "image", ".jpg": "image", ".jpeg": "image",
    ".tiff": "image", ".tif": "image", ".csv": "csv",
    ".txt": "text", ".xml": "xml",
}


# ── Status helpers ──────────────────────────────────────────────────────────

def _fail(doc: Document, error: str, db: Session) -> None:
    """Mark a document as failed with a reason."""
    doc.extraction_status = "failed"
    doc.extraction_error = error[:500]
    db.commit()
    logger.error(f"Pipeline failed for doc {doc.id}: {error}")


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

def create_pending_document(
    filename: str,
    file_bytes: bytes,
    workspace_id: str,
    user_id: str,
    db: Session,
) -> Document:
    """
    Compute the SHA-256 hash, store the file to disk, and create a pending
    Document record. Returns immediately — pipeline runs in the background.
    """
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
        filename=filename,          # overwritten by standardized name in background
        original_filename=filename,
        file_path=str(file_path),
        file_type=file_type,
        sha256_hash=sha256_hash,
        source_type="upload",
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
    raw_extractions: list[dict] = []
    try:
        if schema.parse_strategy == "xml_direct" and is_valid_xml_bytes(file_bytes):
            # XML direct parse — no Claude, confidence = 1.0
            raw_extractions = parse_xml_document(file_bytes, schema)
        else:
            # Claude extraction
            raw_extractions = extract_fields(ocr_text, schema)

        save_extractions(raw_extractions, doc.id, workspace_id, schema.id, db)
    except Exception as e:
        _fail(doc, f"Extraction failed: {e}", db)
        return

    # ── Step 7: Standardized filename ───────────────────────────────────────
    try:
        standardized = generate_standardized_name(
            ocr_text, original_filename, ext.lstrip(".") or "pdf", db
        )
        doc.filename = standardized
    except Exception:
        # Naming failure is non-fatal — keep original filename
        pass

    # ── Step 8: Update FTS search index ─────────────────────────────────────
    # raw_extractions is always list[dict] — no type branching needed
    extra_text = " ".join(
        f"{e.get('field_name', '')} {e.get('field_value', '')}"
        for e in raw_extractions
        if e.get("field_value")
    )
    _update_search_index(doc, ocr_text, extra_text, db)

    doc.extraction_status = "complete"
    db.commit()

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
