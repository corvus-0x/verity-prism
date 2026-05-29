import asyncio
import csv
import io
import json as json_module
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, Response, StreamingResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.document import Document
from app.models.document_extraction import DocumentExtraction
from app.models.user import User
from app.routers.workspaces import get_workspace_or_404
from app.schemas.document import DocumentOut, ExtractionOut
from app.services import audit
from app.services.auth import get_current_user
from app.services.document_pipeline import create_pending_document, process_upload_background
from app.utils.sanitize import escape_csv_cell

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


@router.get("/documents/{document_id}/status/stream")
async def stream_document_status(
    workspace_id: str,
    document_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Stream extraction status updates via Server-Sent Events.
    Polls every 2 seconds. Closes on terminal status or 5-minute timeout.
    """
    get_workspace_or_404(workspace_id, user, db)

    TERMINAL = {"complete", "failed", "no_schema", "needs_review"}

    async def event_generator():
        from sqlalchemy import func as sqlfunc

        from app.database import SessionLocal
        from app.models.document_extraction import DocumentExtraction

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
                    yield f"data: {json_module.dumps({'error': 'not found'})}\n\n"
                    return

                status = doc.extraction_status
                payload = {"extraction_status": status}

                if status == "complete":
                    latest_subq = (
                        stream_db.query(
                            DocumentExtraction.field_name,
                            sqlfunc.max(DocumentExtraction.attempt).label("max_attempt"),
                        )
                        .filter(DocumentExtraction.document_id == document_id)
                        .group_by(DocumentExtraction.field_name)
                        .subquery()
                    )
                    field_count = (
                        stream_db.query(sqlfunc.count(DocumentExtraction.id))
                        .join(
                            latest_subq,
                            (DocumentExtraction.field_name == latest_subq.c.field_name)
                            & (DocumentExtraction.attempt == latest_subq.c.max_attempt),
                        )
                        .filter(DocumentExtraction.document_id == document_id)
                        .scalar()
                    )
                    payload["field_count"] = field_count
                    payload["detected_doc_type"] = doc.detected_doc_type
                elif status == "failed":
                    payload["extraction_error"] = doc.extraction_error

                yield f"data: {json_module.dumps(payload)}\n\n"

                if status in TERMINAL:
                    return

                await asyncio.sleep(interval)
                elapsed += interval

            yield f"data: {json_module.dumps({'extraction_status': 'timeout'})}\n\n"
        finally:
            stream_db.close()

    return StreamingResponse(
        event_generator(),
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


def _latest_extractions(document_id: str, db: Session):
    """Return the latest attempt per field_name for a document."""
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

    extractions = _latest_extractions(document_id, db)
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=["field_name", "field_value", "field_type", "confidence", "attempt"])
    writer.writeheader()
    for e in extractions:
        writer.writerow({
            "field_name": escape_csv_cell(e.field_name),
            "field_value": escape_csv_cell(e.field_value),
            "field_type": escape_csv_cell(e.field_type),
            "confidence": e.confidence,
            "attempt": e.attempt,
        })

    safe_name = doc.filename.replace('"', '')
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}_extractions.csv"'},
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

    extractions = _latest_extractions(document_id, db)
    data = [
        {
            "field_name": e.field_name,
            "field_value": e.field_value or "",
            "field_type": e.field_type,
            "confidence": e.confidence,
            "attempt": e.attempt,
        }
        for e in extractions
    ]
    safe_name = doc.filename.replace('"', '')
    return Response(
        content=json_module.dumps(data, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{safe_name}_extractions.json"'},
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
        Document.is_deleted == False,
    ).all()

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=[
        "document_filename", "document_type",
        "field_name", "field_value", "field_type", "confidence", "attempt",
    ])
    writer.writeheader()
    for doc in docs:
        for e in _latest_extractions(doc.id, db):
            writer.writerow({
                "document_filename": escape_csv_cell(doc.filename),
                "document_type": escape_csv_cell(doc.detected_doc_type or ""),
                "field_name": escape_csv_cell(e.field_name),
                "field_value": escape_csv_cell(e.field_value),
                "field_type": escape_csv_cell(e.field_type),
                "confidence": e.confidence,
                "attempt": e.attempt,
            })

    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="workspace_extractions.csv"'},
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
        Document.is_deleted == False,
    ).all()

    data = []
    for doc in docs:
        for e in _latest_extractions(doc.id, db):
            data.append({
                "document_filename": doc.filename,
                "document_type": doc.detected_doc_type or "",
                "field_name": e.field_name,
                "field_value": e.field_value or "",
                "field_type": e.field_type,
                "confidence": e.confidence,
                "attempt": e.attempt,
            })

    return Response(
        content=json_module.dumps(data, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": 'attachment; filename="workspace_extractions.json"'},
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
