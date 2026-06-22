"""
Observability dashboard endpoints — platform-level extraction quality metrics.
All endpoints require auth. Computation lives in observability_service.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.schemas.observability import (
    AutomationRateOut,
    ClassificationDetailsOut,
    CurrentProcessingOut,
    VolumeOut,
)
from app.services import observability_service
from app.services.auth import get_current_user

router = APIRouter(prefix="/observability", tags=["observability"])


@router.get("/automation-rate", response_model=AutomationRateOut)
def get_automation_rate(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Straight-through processing rate across all non-deleted documents."""
    return observability_service.automation_rate(db, user.id)


@router.get("/volume", response_model=VolumeOut)
def get_volume(
    days: int = Query(default=30, ge=1, le=365),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Daily inbound and completed document counts for the last N days."""
    return observability_service.volume(db, user.id, days)


@router.get("/classification-details", response_model=ClassificationDetailsOut)
def get_classification_details(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Per-schema accuracy metrics — avg AI confidence, avg OCR confidence, retry/correction rates."""
    return observability_service.classification_details(db, user.id)


@router.get("/current-processing", response_model=CurrentProcessingOut)
def get_current_processing(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Count of documents currently pending or awaiting human review."""
    return observability_service.current_processing(db, user.id)
