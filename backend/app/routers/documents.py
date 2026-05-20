from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.document import Document
from app.models.document_extraction import DocumentExtraction
from app.models.user import User
from app.schemas.document import DocumentOut, ExtractionOut
from app.services.auth import get_current_user
from app.services.document_pipeline import create_pending_document, process_upload_background
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
    return db.query(Document).filter(Document.workspace_id == workspace_id).all()


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
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    get_workspace_or_404(workspace_id, user, db)
    return db.query(DocumentExtraction).filter(
        DocumentExtraction.document_id == document_id
    ).all()
