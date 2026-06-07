"""
Export Service — document and workspace data export (CSV, JSON) and SSE streaming.

Routers are thin: they call these functions and wrap results in Response/StreamingResponse.
All formatting and query logic lives here.
"""
import asyncio
import csv
import io
import json
import logging

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.document import Document
from app.models.document_extraction import DocumentExtraction
from app.utils.sanitize import escape_csv_cell

logger = logging.getLogger(__name__)


def latest_extractions(document_id: str, db: Session) -> list[DocumentExtraction]:
    """Return one DocumentExtraction per field_name — the highest attempt number."""
    latest_subq = (
        db.query(
            DocumentExtraction.field_name,
            func.max(DocumentExtraction.attempt).label("max_attempt"),
        )
        .filter(DocumentExtraction.document_id == document_id)
        .group_by(DocumentExtraction.field_name)
        .subquery()
    )
    return (
        db.query(DocumentExtraction)
        .join(
            latest_subq,
            (DocumentExtraction.field_name == latest_subq.c.field_name)
            & (DocumentExtraction.attempt == latest_subq.c.max_attempt),
        )
        .filter(DocumentExtraction.document_id == document_id)
        .all()
    )


def build_document_csv(doc: Document, extractions: list[DocumentExtraction]) -> str:
    """Serialize a document's extractions to CSV string (OWASP formula-injection safe)."""
    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=["field_name", "field_value", "field_type", "confidence", "attempt"],
    )
    writer.writeheader()
    for e in extractions:
        writer.writerow({
            "field_name": escape_csv_cell(e.field_name),
            "field_value": escape_csv_cell(e.field_value),
            "field_type": escape_csv_cell(e.field_type),
            "confidence": e.confidence,
            "attempt": e.attempt,
        })
    return output.getvalue()


def build_document_json(doc: Document, extractions: list[DocumentExtraction]) -> str:
    """Serialize a document's extractions to JSON string."""
    return json.dumps(
        [
            {
                "field_name": e.field_name,
                "field_value": e.field_value or "",
                "field_type": e.field_type,
                "confidence": e.confidence,
                "attempt": e.attempt,
            }
            for e in extractions
        ],
        indent=2,
    )


def build_workspace_csv(docs: list[Document], db: Session) -> str:
    """Serialize all extractions across a list of documents to CSV string."""
    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=[
            "document_filename", "document_type",
            "field_name", "field_value", "field_type", "confidence", "attempt",
        ],
    )
    writer.writeheader()
    for doc in docs:
        for e in latest_extractions(doc.id, db):
            writer.writerow({
                "document_filename": escape_csv_cell(doc.filename),
                "document_type": escape_csv_cell(doc.detected_doc_type or ""),
                "field_name": escape_csv_cell(e.field_name),
                "field_value": escape_csv_cell(e.field_value),
                "field_type": escape_csv_cell(e.field_type),
                "confidence": e.confidence,
                "attempt": e.attempt,
            })
    return output.getvalue()


def build_workspace_json(docs: list[Document], db: Session) -> str:
    """Serialize all extractions across a list of documents to JSON string."""
    data = []
    for doc in docs:
        for e in latest_extractions(doc.id, db):
            data.append({
                "document_filename": doc.filename,
                "document_type": doc.detected_doc_type or "",
                "field_name": e.field_name,
                "field_value": e.field_value or "",
                "field_type": e.field_type,
                "confidence": e.confidence,
                "attempt": e.attempt,
            })
    return json.dumps(data, indent=2)


async def document_status_stream(workspace_id: str, document_id: str):
    """Async generator that yields SSE events for a document's extraction status.

    Opens its own DB session so the long-lived poll doesn't block the request session.
    Closes on terminal status (complete/failed/no_schema/needs_review) or 5-min timeout.
    """
    TERMINAL = {"complete", "failed", "no_schema", "needs_review"}
    stream_db = SessionLocal()
    try:
        elapsed = 0
        max_seconds = 300
        interval = 2

        while elapsed < max_seconds:
            stream_db.expire_all()
            doc = stream_db.query(Document).filter(
                Document.id == document_id,
                Document.workspace_id == workspace_id,
            ).first()

            if not doc:
                yield f"data: {json.dumps({'error': 'not found'})}\n\n"
                return

            status = doc.extraction_status
            payload = {"extraction_status": status}

            if status == "complete":
                payload["field_count"] = len(latest_extractions(document_id, stream_db))
                payload["detected_doc_type"] = doc.detected_doc_type
                payload["filename"] = doc.filename
            elif status == "failed":
                payload["extraction_error"] = doc.extraction_error

            yield f"data: {json.dumps(payload)}\n\n"

            if status in TERMINAL:
                return

            await asyncio.sleep(interval)
            elapsed += interval

        yield f"data: {json.dumps({'extraction_status': 'timeout'})}\n\n"
    finally:
        stream_db.close()
