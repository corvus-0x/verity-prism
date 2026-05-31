"""
Observability dashboard endpoints — platform-level extraction quality metrics.
All endpoints require auth. Data comes entirely from existing tables.
"""
from datetime import UTC, date, datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.document import Document
from app.models.document_extraction import DocumentExtraction
from app.models.document_schema import DocumentSchema
from app.models.user import User
from app.schemas.observability import (
    AutomationRateOut,
    ClassificationDetailsOut,
    CurrentProcessingOut,
    DailyVolume,
    SchemaDetail,
    VolumeOut,
)
from app.services.auth import get_current_user

router = APIRouter(prefix="/observability", tags=["observability"])


@router.get("/automation-rate", response_model=AutomationRateOut)
def get_automation_rate(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Straight-through processing rate across all non-deleted documents."""
    rows = (
        db.query(Document.extraction_status, func.count(Document.id))
        .filter(Document.is_deleted == False)
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


@router.get("/volume", response_model=VolumeOut)
def get_volume(
    days: int = Query(default=30, ge=1, le=365),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Daily inbound and completed document counts for the last N days."""
    today = date.today()
    day_list = [today - timedelta(days=i) for i in range(days - 1, -1, -1)]

    cutoff = datetime(today.year, today.month, today.day, tzinfo=UTC) - timedelta(days=days - 1)

    inbound_rows = (
        db.query(
            func.date(Document.uploaded_at).label("d"),
            func.count(Document.id).label("n"),
        )
        .filter(
            Document.is_deleted == False,
            Document.uploaded_at >= cutoff,
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
            Document.is_deleted == False,
            Document.extraction_status == "complete",
            Document.uploaded_at >= cutoff,
        )
        .group_by("d")
        .all()
    )

    inbound_map = {str(r.d): r.n for r in inbound_rows}
    completed_map = {str(r.d): r.n for r in completed_rows}

    return VolumeOut(days=[
        DailyVolume(
            date=str(d),
            inbound=inbound_map.get(str(d), 0),
            completed=completed_map.get(str(d), 0),
        )
        for d in day_list
    ])


@router.get("/classification-details", response_model=ClassificationDetailsOut)
def get_classification_details(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Per-schema accuracy metrics — avg AI confidence, avg OCR confidence, retry/correction rates."""
    from sqlalchemy import case  # noqa: F401 — imported here to keep top-level imports minimal

    schema_rows = (
        db.query(DocumentSchema.document_type, DocumentSchema.id)
        .filter(DocumentSchema.is_active == True)
        .all()
    )

    if not schema_rows:
        return ClassificationDetailsOut(schemas=[])

    schema_ids = [s.id for s in schema_rows]
    schema_type_map = {s.id: s.document_type for s in schema_rows}

    # Doc counts per schema
    doc_counts = dict(
        db.query(Document.schema_id, func.count(Document.id))
        .filter(Document.schema_id.in_(schema_ids), Document.is_deleted == False)
        .group_by(Document.schema_id)
        .all()
    )

    # Avg confidences (attempt=1 only)
    conf_rows = (
        db.query(
            DocumentExtraction.schema_id,
            func.avg(DocumentExtraction.confidence).label("avg_ai"),
            func.avg(DocumentExtraction.ocr_confidence).label("avg_ocr"),
        )
        .filter(DocumentExtraction.schema_id.in_(schema_ids), DocumentExtraction.attempt == 1)
        .group_by(DocumentExtraction.schema_id)
        .all()
    )
    conf_map = {r.schema_id: (float(r.avg_ai or 0), float(r.avg_ocr or 0)) for r in conf_rows}

    # Retry docs (attempt=2) per schema
    retry_rows = (
        db.query(DocumentExtraction.schema_id, func.count(func.distinct(DocumentExtraction.document_id)))
        .filter(DocumentExtraction.schema_id.in_(schema_ids), DocumentExtraction.attempt == 2)
        .group_by(DocumentExtraction.schema_id)
        .all()
    )
    retry_map = dict(retry_rows)

    # Correction docs (attempt=3) per schema
    correction_rows = (
        db.query(DocumentExtraction.schema_id, func.count(func.distinct(DocumentExtraction.document_id)))
        .filter(DocumentExtraction.schema_id.in_(schema_ids), DocumentExtraction.attempt == 3)
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
        details.append(SchemaDetail(
            document_type=doc_type,
            total_documents=doc_count,
            avg_ai_confidence=round(avg_ai, 4),
            avg_ocr_confidence=round(avg_ocr, 4),
            retry_rate=round(retry_docs / doc_count, 4),
            correction_rate=round(correction_docs / doc_count, 4),
        ))

    return ClassificationDetailsOut(schemas=details)


@router.get("/current-processing", response_model=CurrentProcessingOut)
def get_current_processing(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Count of documents currently pending or awaiting human review."""
    rows = (
        db.query(Document.extraction_status, func.count(Document.id))
        .filter(
            Document.is_deleted == False,
            Document.extraction_status.in_(["pending", "needs_review"]),
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
