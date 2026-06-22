from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_workspace_or_404
from app.models.user import User
from app.schemas.lead import LeadCreate, LeadOut, LeadUpdate
from app.services import lead_service
from app.services.auth import get_current_user

router = APIRouter(prefix="/workspaces/{workspace_id}/leads", tags=["leads"])


@router.post("/", response_model=LeadOut, status_code=201)
def create_lead(
    workspace_id: str,
    payload: LeadCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    get_workspace_or_404(workspace_id, user, db)
    return lead_service.create_lead(db, workspace_id, user.id, payload)


@router.get("/", response_model=list[LeadOut])
def list_leads(
    workspace_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    get_workspace_or_404(workspace_id, user, db)
    return lead_service.list_leads(db, workspace_id)


@router.patch("/{lead_id}", response_model=LeadOut)
def update_lead(
    workspace_id: str,
    lead_id: str,
    payload: LeadUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    get_workspace_or_404(workspace_id, user, db)
    lead = lead_service.update_lead(db, workspace_id, lead_id, user.id, payload)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    return lead
