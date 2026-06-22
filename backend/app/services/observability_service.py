"""Observability metrics — platform-level extraction quality aggregates.

All queries are scoped to the workspaces the caller owns and exclude soft-deleted
documents. Pure reads over existing tables; no writes.
"""

from datetime import UTC, date, datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.document_extraction import DocumentExtraction
from app.models.document_schema import DocumentSchema
from app.models.workspace import Workspace
from app.schemas.observability import (
    AutomationRateOut,
    ClassificationDetailsOut,
    CurrentProcessingOut,
    DailyVolume,
    SchemaDetail,
    VolumeOut,
)


def automation_rate(db: Session, user_id: str) -> AutomationRateOut:
    """Straight-through processing rate across the caller's non-deleted documents."""
    caller_ws = db.query(Workspace.id).filter(Workspace.created_by == user_id).scalar_subquery()
    rows = (
        db.query(Document.extraction_status, func.count(Document.id))
        .filter(Document.is_deleted == False, Document.workspace_id.in_(caller_ws))  # noqa: E712
        .group_by(Document.extraction_status)
        .all()
    )
    counts = {status: n for status, n in rows}
    automated = counts.get("complete", 0)
    needs_review = counts.get("needs_review", 0)
    failed = counts.get("failed", 0)
    total = sum(counts.values())
    return AutomationRateOut(
        total=total,
        automated=automated,
        needs_review=needs_review,
        failed=failed,
        automation_rate=round(automated / total, 4) if total else 0.0,
    )


def volume(db: Session, user_id: str, days: int) -> VolumeOut:
    """Daily inbound and completed document counts for the last N days."""
    today = date.today()
    day_list = [today - timedelta(days=i) for i in range(days - 1, -1, -1)]
    cutoff = datetime(today.year, today.month, today.day, tzinfo=UTC) - timedelta(days=days - 1)

    caller_ws = db.query(Workspace.id).filter(Workspace.created_by == user_id).scalar_subquery()

    inbound_rows = (
        db.query(
            func.date(Document.uploaded_at).label("d"),
            func.count(Document.id).label("n"),
        )
        .filter(
            Document.is_deleted == False,  # noqa: E712
            Document.uploaded_at >= cutoff,
            Document.workspace_id.in_(caller_ws),
        )
        .group_by("d")
        .all()
    )
    completed_rows = (
        db.query(
            func.date(Document.uploaded_at).label("d"),
            func.count(Document.id).label("n"),
        )
        .filter(
            Document.is_deleted == False,  # noqa: E712
            Document.extraction_status == "complete",
            Document.uploaded_at >= cutoff,
            Document.workspace_id.in_(caller_ws),
        )
        .group_by("d")
        .all()
    )

    inbound_map = {str(r.d): r.n for r in inbound_rows}
    completed_map = {str(r.d): r.n for r in completed_rows}

    return VolumeOut(
        days=[
            DailyVolume(
                date=str(d),
                inbound=inbound_map.get(str(d), 0),
                completed=completed_map.get(str(d), 0),
            )
            for d in day_list
        ]
    )


def classification_details(db: Session, user_id: str) -> ClassificationDetailsOut:
    """Per-schema accuracy metrics — avg AI/OCR confidence, retry/correction rates."""
    schema_rows = (
        db.query(DocumentSchema.document_type, func.max(DocumentSchema.id).label("id"))
        .filter(DocumentSchema.is_active == True)  # noqa: E712
        .group_by(DocumentSchema.document_type)
        .all()
    )
    if not schema_rows:
        return ClassificationDetailsOut(schemas=[])

    schema_ids = [s.id for s in schema_rows]
    schema_type_map = {s.id: s.document_type for s in schema_rows}

    caller_ws = db.query(Workspace.id).filter(Workspace.created_by == user_id).scalar_subquery()

    doc_counts = dict(
        db.query(Document.schema_id, func.count(Document.id))
        .filter(
            Document.schema_id.in_(schema_ids),
            Document.is_deleted == False,  # noqa: E712
            Document.workspace_id.in_(caller_ws),
        )
        .group_by(Document.schema_id)
        .all()
    )

    caller_doc_ids = (
        db.query(Document.id)
        .filter(Document.is_deleted == False, Document.workspace_id.in_(caller_ws))  # noqa: E712
        .scalar_subquery()
    )

    conf_rows = (
        db.query(
            DocumentExtraction.schema_id,
            func.avg(DocumentExtraction.confidence).label("avg_ai"),
            func.avg(DocumentExtraction.ocr_confidence).label("avg_ocr"),
        )
        .filter(
            DocumentExtraction.schema_id.in_(schema_ids),
            DocumentExtraction.attempt == 1,
            DocumentExtraction.document_id.in_(caller_doc_ids),
        )
        .group_by(DocumentExtraction.schema_id)
        .all()
    )
    conf_map = {r.schema_id: (float(r.avg_ai or 0), float(r.avg_ocr or 0)) for r in conf_rows}

    retry_rows = (
        db.query(
            DocumentExtraction.schema_id, func.count(func.distinct(DocumentExtraction.document_id))
        )
        .filter(
            DocumentExtraction.schema_id.in_(schema_ids),
            DocumentExtraction.attempt == 2,
            DocumentExtraction.document_id.in_(caller_doc_ids),
        )
        .group_by(DocumentExtraction.schema_id)
        .all()
    )
    retry_map = dict(retry_rows)

    correction_rows = (
        db.query(
            DocumentExtraction.schema_id, func.count(func.distinct(DocumentExtraction.document_id))
        )
        .filter(
            DocumentExtraction.schema_id.in_(schema_ids),
            DocumentExtraction.attempt == 3,
            DocumentExtraction.document_id.in_(caller_doc_ids),
        )
        .group_by(DocumentExtraction.schema_id)
        .all()
    )
    correction_map = dict(correction_rows)

    details = []
    for schema_id, doc_type in schema_type_map.items():
        doc_count = doc_counts.get(schema_id, 0)
        if doc_count == 0:
            continue
        avg_ai, avg_ocr = conf_map.get(schema_id, (0.0, 0.0))
        retry_docs = retry_map.get(schema_id, 0)
        correction_docs = correction_map.get(schema_id, 0)
        details.append(
            SchemaDetail(
                document_type=doc_type,
                total_documents=doc_count,
                avg_ai_confidence=round(avg_ai, 4),
                avg_ocr_confidence=round(avg_ocr, 4),
                retry_rate=round(retry_docs / doc_count, 4),
                correction_rate=round(correction_docs / doc_count, 4),
            )
        )

    return ClassificationDetailsOut(schemas=details)


def current_processing(db: Session, user_id: str) -> CurrentProcessingOut:
    """Count of the caller's documents currently pending or awaiting human review."""
    caller_ws = db.query(Workspace.id).filter(Workspace.created_by == user_id).scalar_subquery()
    rows = (
        db.query(Document.extraction_status, func.count(Document.id))
        .filter(
            Document.is_deleted == False,  # noqa: E712
            Document.extraction_status.in_(["pending", "needs_review"]),
            Document.workspace_id.in_(caller_ws),
        )
        .group_by(Document.extraction_status)
        .all()
    )
    counts = {status: n for status, n in rows}
    pending = counts.get("pending", 0)
    needs_review = counts.get("needs_review", 0)
    return CurrentProcessingOut(
        pending=pending,
        needs_review=needs_review,
        total_active=pending + needs_review,
    )
