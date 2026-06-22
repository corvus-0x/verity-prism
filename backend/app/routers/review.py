from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_workspace_or_404
from app.models.user import User
from app.schemas.document import ExtractionCreateIn, ExtractionOut
from app.schemas.review import (
    ExtractionCorrectionIn,
    ExtractionCorrectionOut,
    FlagDocumentIn,
    FlagDocumentOut,
    ReviewQueueItem,
)
from app.services import review_service
from app.services.auth import get_current_user

router = APIRouter(prefix="/workspaces/{workspace_id}", tags=["review"])


@router.get("/review-queue", response_model=list[ReviewQueueItem])
def get_review_queue(
    workspace_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Return documents with extraction_status='needs_review' in this workspace.
    Includes a count of fields still below threshold and not yet human-corrected.
    """
    get_workspace_or_404(workspace_id, user, db)
    return review_service.get_review_queue(db, workspace_id)


@router.patch(
    "/documents/{document_id}/extractions/{extraction_id}/correct",
    response_model=ExtractionCorrectionOut,
)
def correct_extraction(
    workspace_id: str,
    document_id: str,
    extraction_id: str,
    body: ExtractionCorrectionIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Apply a human correction to a low-confidence field.
    Inserts a new row with attempt=3 and confidence=1.0 — the original rows are preserved.
    If all fields are now corrected, flips document status back to 'complete'.
    """
    get_workspace_or_404(
        workspace_id, user, db, required_roles={"owner", "analyst"}, require_active=True
    )
    try:
        return review_service.correct_extraction(
            db,
            workspace_id,
            document_id,
            extraction_id,
            user.id,
            body,
        )
    except review_service.ReviewError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from e


@router.patch(
    "/documents/{document_id}/flag",
    response_model=FlagDocumentOut,
)
def flag_document(
    workspace_id: str,
    document_id: str,
    body: FlagDocumentIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Store a structured rejection reason on a document.
    Flag reason and note travel with the document through processing.
    Does not change extraction_status — use the correction endpoint to resolve fields.
    """
    get_workspace_or_404(
        workspace_id, user, db, required_roles={"owner", "analyst"}, require_active=True
    )
    try:
        return review_service.flag_document(
            db,
            workspace_id,
            document_id,
            user.id,
            body.flag_reason,
            body.flag_note,
        )
    except review_service.ReviewError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from e


@router.post(
    "/documents/{document_id}/extractions",
    response_model=ExtractionOut,
    status_code=201,
)
def create_extraction(
    workspace_id: str,
    document_id: str,
    body: ExtractionCreateIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Create a new attempt=3 extraction row for a field with no prior extraction.
    Used by the review pane when an operator enters a value for a field the
    pipeline never extracted.
    """
    get_workspace_or_404(
        workspace_id, user, db, required_roles={"owner", "analyst"}, require_active=True
    )
    try:
        return review_service.create_extraction(db, workspace_id, document_id, user.id, body)
    except review_service.ReviewError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail) from e
