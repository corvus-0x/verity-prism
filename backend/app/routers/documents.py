from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, UploadFile, File
from fastapi.responses import FileResponse
from pathlib import Path
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.config import settings
from app.database import get_db
from app.models.document import Document
from app.models.document_extraction import DocumentExtraction
from app.models.user import User
from app.schemas.document import DocumentOut, ExtractionOut
from app.services.auth import get_current_user
from app.services.document_pipeline import create_pending_document, process_upload_background
from app.services import audit
from app.routers.workspaces import get_workspace_or_404

router = APIRouter(prefix="/workspaces/{workspace_id}", tags=["documents"])


@router.post("/documents", response_model=DocumentOut, status_code=201)
def upload_document(
    workspace_id: str,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Upload a document. Returns immediately with a pending record.
    The extraction pipeline runs in the background after the response is sent.

    Poll GET /documents/{id} to check extraction_status:
      pending   — pipeline has not started yet
      complete  — all fields extracted successfully
      failed    — a pipeline step failed; check extraction_error for details
      no_schema — document type has no schema; an investigation lead was created
    """
    get_workspace_or_404(workspace_id, user, db)

    # Read file bytes NOW — UploadFile is not available after the response is sent
    file_bytes = file.file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")
    if len(file_bytes) > settings.max_upload_bytes:
        raise HTTPException(status_code=413, detail=f"File too large. Maximum size is {settings.max_upload_bytes // 1_048_576} MB.")

    # Step 1–2: hash + store + create pending record (synchronous)
    doc = create_pending_document(
        filename=file.filename,
        file_bytes=file_bytes,
        workspace_id=workspace_id,
        user_id=user.id,
        db=db,
    )

    # Steps 3–9 run after the HTTP response is sent
    background_tasks.add_task(
        process_upload_background,
        doc.id,
        file_bytes,
        file.filename,
        workspace_id,
        user.id,
    )

    return doc


@router.get("/documents", response_model=list[DocumentOut])
def list_documents(
    workspace_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    get_workspace_or_404(workspace_id, user, db)
    return db.query(Document).filter(
        Document.workspace_id == workspace_id,
        Document.is_deleted == False,
    ).all()


@router.get("/documents/{document_id}", response_model=DocumentOut)
def get_document(
    workspace_id: str,
    document_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    get_workspace_or_404(workspace_id, user, db)
    doc = db.query(Document).filter(
        Document.id == document_id, Document.workspace_id == workspace_id
    ).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


@router.get("/documents/{document_id}/extractions", response_model=list[ExtractionOut])
def list_extractions(
    workspace_id: str,
    document_id: str,
    include_history: bool = Query(default=False),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Return extracted fields for a document.
    Default: one row per field_name (the latest attempt).
    ?include_history=true: all rows for all attempts, ordered by field_name then attempt.
    """
    get_workspace_or_404(workspace_id, user, db)

    if include_history:
        return (
            db.query(DocumentExtraction)
            .filter(DocumentExtraction.document_id == document_id)
            .order_by(DocumentExtraction.field_name, DocumentExtraction.attempt)
            .all()
        )

    # Latest attempt per field_name via subquery — prevents duplicate field
    # names appearing once attempt > 1 rows exist in the table.
    latest_attempt_subq = (
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
            latest_attempt_subq,
            (DocumentExtraction.field_name == latest_attempt_subq.c.field_name)
            & (DocumentExtraction.attempt == latest_attempt_subq.c.max_attempt),
        )
        .filter(DocumentExtraction.document_id == document_id)
        .all()
    )


_MEDIA_TYPES = {
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".tiff": "image/tiff",
    ".tif": "image/tiff",
    ".xml": "application/xml",
}


@router.get("/documents/{document_id}/file")
def get_document_file(
    workspace_id: str,
    document_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Serve the raw source file for a document."""
    get_workspace_or_404(workspace_id, user, db)
    doc = db.query(Document).filter(
        Document.id == document_id,
        Document.workspace_id == workspace_id,
        Document.is_deleted == False,
    ).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    file_path = Path(doc.file_path)
    if not file_path.exists():
        audit.log(
            db,
            action="document_file_missing",
            workspace_id=workspace_id,
            entity_type="document",
            entity_id=document_id,
        )
        raise HTTPException(status_code=404, detail="File not found on disk")

    audit.log(
        db,
        action="document_file_accessed",
        user_id=user.id,
        workspace_id=workspace_id,
        entity_type="document",
        entity_id=document_id,
    )

    media_type = _MEDIA_TYPES.get(file_path.suffix.lower(), "application/octet-stream")
    return FileResponse(str(file_path), media_type=media_type)
