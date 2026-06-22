from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_workspace_or_404
from app.models.user import User
from app.schemas.finding import FindingCreate, FindingOut, FindingUpdate, SignalTypeOut
from app.services import finding_service
from app.services.auth import get_current_user

router = APIRouter(tags=["findings"])


@router.get("/signal-types", response_model=list[SignalTypeOut])
def list_signal_types(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return finding_service.list_signal_types(db)


@router.post("/workspaces/{workspace_id}/findings", response_model=FindingOut, status_code=201)
def create_finding(
    workspace_id: str,
    payload: FindingCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    get_workspace_or_404(workspace_id, user, db)
    return finding_service.create_finding(db, workspace_id, user.id, payload)


@router.get("/workspaces/{workspace_id}/findings", response_model=list[FindingOut])
def list_findings(
    workspace_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    get_workspace_or_404(workspace_id, user, db)
    return finding_service.list_findings(db, workspace_id)


@router.patch("/workspaces/{workspace_id}/findings/{finding_id}", response_model=FindingOut)
def update_finding(
    workspace_id: str,
    finding_id: str,
    payload: FindingUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    get_workspace_or_404(workspace_id, user, db)
    finding = finding_service.update_finding(db, workspace_id, finding_id, user.id, payload)
    if not finding:
        raise HTTPException(status_code=404, detail="Finding not found")
    return finding
