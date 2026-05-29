from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.lead import InvestigationLead
from app.models.user import User
from app.routers.workspaces import get_workspace_or_404
from app.schemas.lead import LeadCreate, LeadOut, LeadUpdate
from app.services import audit
from app.services.auth import get_current_user

router = APIRouter(prefix="/workspaces/{workspace_id}/leads", tags=["leads"])


@router.post("/", response_model=LeadOut, status_code=201)
def create_lead(workspace_id: str, payload: LeadCreate,
                db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    get_workspace_or_404(workspace_id, user, db)
    lead = InvestigationLead(**payload.model_dump(), workspace_id=workspace_id)
    db.add(lead)
    db.commit()
    db.refresh(lead)
    audit.log(db, action="created", user_id=user.id, workspace_id=workspace_id,
              entity_type="lead", entity_id=lead.id)
    return lead


@router.get("/", response_model=list[LeadOut])
def list_leads(workspace_id: str, db: Session = Depends(get_db),
               user: User = Depends(get_current_user)):
    get_workspace_or_404(workspace_id, user, db)
    return db.query(InvestigationLead).filter(
        InvestigationLead.workspace_id == workspace_id
    ).all()


@router.patch("/{lead_id}", response_model=LeadOut)
def update_lead(workspace_id: str, lead_id: str, payload: LeadUpdate,
                db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    get_workspace_or_404(workspace_id, user, db)
    lead = db.query(InvestigationLead).filter(
        InvestigationLead.id == lead_id, InvestigationLead.workspace_id == workspace_id
    ).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(lead, field, value)
    if payload.status in ("complete", "dead_end"):
        lead.completed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(lead)
    audit.log(db, action="updated", user_id=user.id, workspace_id=workspace_id,
              entity_type="lead", entity_id=lead.id)
    return lead
