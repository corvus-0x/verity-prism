from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.finding import Finding, SignalType
from app.models.user import User
from app.deps import get_workspace_or_404
from app.schemas.finding import FindingCreate, FindingOut, FindingUpdate, SignalTypeOut
from app.services import audit
from app.services.auth import get_current_user

router = APIRouter(tags=["findings"])

SIGNAL_TYPES_SEED = [
    {"code": "SR-003", "name": "VALUATION_ANOMALY",
     "description": "Property purchased significantly above or below appraised value",
     "severity": "critical", "relevant_to": ["AG", "IRS"]},
    {"code": "SR-004", "name": "UCC_BURST",
     "description": "Multiple UCC amendments filed within minutes — coordinated lien activity",
     "severity": "high", "relevant_to": ["FCA", "FBI"]},
    {"code": "SR-005", "name": "ZERO_CONSIDERATION",
     "description": "Property transferred for $0 to a private party",
     "severity": "critical", "relevant_to": ["AG", "IRS"]},
    {"code": "SR-015", "name": "DEED_TITLE_DEFECT",
     "description": "Deed executed in favor of an entity that did not legally exist at the time",
     "severity": "high", "relevant_to": ["AG"]},
    {"code": "SR-021", "name": "REVENUE_SPIKE",
     "description": "Organization revenue increased more than 500% year-over-year",
     "severity": "medium", "relevant_to": ["IRS"]},
    {"code": "SR-024", "name": "CHARITY_CONDUIT",
     "description": "Charitable funds used to fund improvements on privately-owned property",
     "severity": "critical", "relevant_to": ["IRS", "AG", "FBI"]},
    {"code": "SR-025", "name": "FALSE_DISCLOSURE",
     "description": "Organization disclosed related-party transactions in one year then denied them in all subsequent years while transactions continued",
     "severity": "critical", "relevant_to": ["IRS", "AG"]},
    {"code": "SR-026", "name": "CONSTRUCTION_OVERAGE",
     "description": "Construction permit value exceeds total organization revenue for that period",
     "severity": "high", "relevant_to": ["IRS", "AG"]},
]

def seed_signal_types(db: Session):
    if db.query(SignalType).count() == 0:
        for s in SIGNAL_TYPES_SEED:
            db.add(SignalType(**s))
        db.commit()

@router.get("/signal-types", response_model=list[SignalTypeOut])
def list_signal_types(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    seed_signal_types(db)
    return db.query(SignalType).all()

@router.post("/workspaces/{workspace_id}/findings", response_model=FindingOut, status_code=201)
def create_finding(workspace_id: str, payload: FindingCreate,
                   db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    get_workspace_or_404(workspace_id, user, db)
    finding = Finding(**payload.model_dump(), workspace_id=workspace_id, created_by=user.id)
    db.add(finding)
    db.commit()
    db.refresh(finding)
    audit.log(db, action="created", user_id=user.id, workspace_id=workspace_id,
              entity_type="finding", entity_id=finding.id,
              after_state={"title": finding.title, "severity": finding.severity})
    return finding

@router.get("/workspaces/{workspace_id}/findings", response_model=list[FindingOut])
def list_findings(workspace_id: str, db: Session = Depends(get_db),
                  user: User = Depends(get_current_user)):
    get_workspace_or_404(workspace_id, user, db)
    return db.query(Finding).filter(Finding.workspace_id == workspace_id).all()

@router.patch("/workspaces/{workspace_id}/findings/{finding_id}", response_model=FindingOut)
def update_finding(workspace_id: str, finding_id: str, payload: FindingUpdate,
                   db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    get_workspace_or_404(workspace_id, user, db)
    finding = db.query(Finding).filter(
        Finding.id == finding_id, Finding.workspace_id == workspace_id
    ).first()
    if not finding:
        raise HTTPException(status_code=404, detail="Finding not found")
    before = {"status": finding.status}
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(finding, field, value)
    db.commit()
    db.refresh(finding)
    audit.log(db, action="updated", user_id=user.id, workspace_id=workspace_id,
              entity_type="finding", entity_id=finding.id,
              before_state=before, after_state={"status": finding.status})
    return finding
