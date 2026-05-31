"""
Observability dashboard endpoints — platform-level extraction quality metrics.
All endpoints require auth. Data comes entirely from existing tables.
"""
from datetime import UTC, date, datetime, timedelta

from fastapi import APIRouter, Depends
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
    days: int = 30,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Daily inbound and completed document counts for the last N days."""
    today = date.today()
    day_list = [today - timedelta(days=i) for i in range(days - 1, -1, -1)]

    cutoff = datetime(today.year, today.month, today.day, tzinfo=UTC) - timedelta(days=days)

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
    schema_types = (
        db.query(DocumentSchema.document_type, DocumentSchema.id)
        .filter(DocumentSchema.is_active == True)
        .all()
    )

    details = []
    for doc_type, schema_id in schema_types:
        doc_count = (
            db.query(func.count(Document.id))
            .filter(Document.schema_id == schema_id, Document.is_deleted == False)
            .scalar()
        ) or 0

        if doc_count == 0:
            continue

        avg_ai = (
            db.query(func.avg(DocumentExtraction.confidence))
            .filter(DocumentExtraction.schema_id == schema_id, DocumentExtraction.attempt == 1)
            .scalar()
        ) or 0.0

        avg_ocr = (
            db.query(func.avg(DocumentExtraction.ocr_confidence))
            .filter(DocumentExtraction.schema_id == schema_id, DocumentExtraction.attempt == 1)
            .scalar()
        ) or 0.0

        retry_docs = (
            db.query(func.count(func.distinct(DocumentExtraction.document_id)))
            .filter(DocumentExtraction.schema_id == schema_id, DocumentExtraction.attempt == 2)
            .scalar()
        ) or 0

        correction_docs = (
            db.query(func.count(func.distinct(DocumentExtraction.document_id)))
            .filter(DocumentExtraction.schema_id == schema_id, DocumentExtraction.attempt == 3)
            .scalar()
        ) or 0

        details.append(SchemaDetail(
            document_type=doc_type,
            total_documents=doc_count,
            avg_ai_confidence=round(float(avg_ai), 4),
            avg_ocr_confidence=round(float(avg_ocr), 4),
            retry_rate=round(retry_docs / doc_count, 4) if doc_count else 0.0,
            correction_rate=round(correction_docs / doc_count, 4) if doc_count else 0.0,
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
