from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, Response, StreamingResponse
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.deps import get_workspace_or_404
from app.models.document import Document
from app.models.document_extraction import DocumentExtraction
from app.models.user import User
from app.schemas.document import DocumentOut, ExtractionOut
from app.services import audit, export_service
from app.services.auth import get_current_user
from app.services.document_pipeline import (
    EXTENSION_TO_TYPE,
    create_pending_document,
    process_upload_background,
)
from app.utils.sanitize import content_disposition

router = APIRouter(prefix="/workspaces/{workspace_id}", tags=["documents"])

# Upload/serve security policy (M3): only accept known types, and serve
# user-uploaded files without letting the browser MIME-sniff them into XSS.
ALLOWED_UPLOAD_EXTENSIONS = set(EXTENSION_TO_TYPE)
INLINE_SUFFIXES = {".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".tif"}


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
        raise HTTPException(
            status_code=413, detail=f"File too large. Maximum size is {settings.max_upload_bytes // 1_048_576} MB.")

    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_UPLOAD_EXTENSIONS:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type '{ext or '(none)'}'. Accepted: "
            f"{', '.join(sorted(ALLOWED_UPLOAD_EXTENSIONS))}",
        )

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
        ~Document.is_deleted,
    ).all()


@router.get("/documents/{document_id}/status/stream")
async def stream_document_status(
    workspace_id: str,
    document_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Stream extraction status updates via Server-Sent Events."""
    get_workspace_or_404(workspace_id, user, db)
    return StreamingResponse(
        export_service.document_status_stream(workspace_id, document_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


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

    return export_service.latest_extractions(document_id, db)


@router.get("/documents/{document_id}/extractions.csv")
def download_extractions_csv(
    workspace_id: str,
    document_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Download extracted fields for one document as CSV (latest attempt per field)."""
    get_workspace_or_404(workspace_id, user, db)
    doc = db.query(Document).filter(
        Document.id == document_id, Document.workspace_id == workspace_id
    ).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    extractions = export_service.latest_extractions(document_id, db)
    content = export_service.build_document_csv(doc, extractions)
    return Response(
        content=content,
        media_type="text/csv",
        headers={"Content-Disposition": content_disposition(
            f"{doc.filename}_extractions.csv", "attachment")},
    )


@router.get("/documents/{document_id}/extractions.json")
def download_extractions_json(
    workspace_id: str,
    document_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Download extracted fields for one document as JSON (latest attempt per field)."""
    get_workspace_or_404(workspace_id, user, db)
    doc = db.query(Document).filter(
        Document.id == document_id, Document.workspace_id == workspace_id
    ).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    extractions = export_service.latest_extractions(document_id, db)
    content = export_service.build_document_json(doc, extractions)
    return Response(
        content=content,
        media_type="application/json",
        headers={"Content-Disposition": content_disposition(
            f"{doc.filename}_extractions.json", "attachment")},
    )


@router.get("/extractions.csv")
def download_workspace_extractions_csv(
    workspace_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Download all extractions across the workspace as CSV."""
    get_workspace_or_404(workspace_id, user, db)
    docs = db.query(Document).filter(
        Document.workspace_id == workspace_id,
        Document.extraction_status.in_(["complete", "needs_review"]),
        ~Document.is_deleted,
    ).all()
    content = export_service.build_workspace_csv(docs, db)
    return Response(
        content=content,
        media_type="text/csv",
        headers={
            "Content-Disposition": 'attachment; filename="workspace_extractions.csv"'},
    )


@router.get("/extractions.json")
def download_workspace_extractions_json(
    workspace_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Download all extractions across the workspace as JSON."""
    get_workspace_or_404(workspace_id, user, db)
    docs = db.query(Document).filter(
        Document.workspace_id == workspace_id,
        Document.extraction_status.in_(["complete", "needs_review"]),
        ~Document.is_deleted,
    ).all()
    content = export_service.build_workspace_json(docs, db)
    return Response(
        content=content,
        media_type="application/json",
        headers={
            "Content-Disposition": 'attachment; filename="workspace_extractions.json"'},
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
        ~Document.is_deleted,
    ).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    file_path = Path(doc.file_path)
    if not file_path.exists():
        audit.log(
            db,
            action="document_file_missing",
            user_id=user.id,
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

    suffix = file_path.suffix.lower()
    media_type = _MEDIA_TYPES.get(suffix, "application/octet-stream")
    disposition = "inline" if suffix in INLINE_SUFFIXES else "attachment"
    return FileResponse(
        str(file_path),
        media_type=media_type,
        headers={
            "X-Content-Type-Options": "nosniff",
            "Content-Disposition": content_disposition(doc.original_filename, disposition),
        },
    )
