from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models.lead import InvestigationLead
from app.schemas.lead import LeadCreate, LeadUpdate
from app.services import audit


def create_lead(
    db: Session, workspace_id: str, user_id: str, payload: LeadCreate
) -> InvestigationLead:
    """Create an investigation lead and write an audit entry."""
    lead = InvestigationLead(**payload.model_dump(), workspace_id=workspace_id)
    db.add(lead)
    db.flush()
    db.refresh(lead)
    audit.log(
        db,
        action="created",
        user_id=user_id,
        workspace_id=workspace_id,
        entity_type="lead",
        entity_id=lead.id,
    )
    return lead


def list_leads(db: Session, workspace_id: str) -> list[InvestigationLead]:
    """List active (non-deleted) leads in a workspace."""
    return (
        db.query(InvestigationLead)
        .filter(
            InvestigationLead.workspace_id == workspace_id,
            InvestigationLead.is_deleted == False,  # noqa: E712
        )
        .all()
    )


def update_lead(
    db: Session, workspace_id: str, lead_id: str, user_id: str, payload: LeadUpdate
) -> InvestigationLead | None:
    """Apply a partial update to a lead; return None if not found.
    Stamps completed_at when the lead reaches a terminal status."""
    lead = (
        db.query(InvestigationLead)
        .filter(
            InvestigationLead.id == lead_id,
            InvestigationLead.workspace_id == workspace_id,
            InvestigationLead.is_deleted == False,  # noqa: E712
        )
        .first()
    )
    if not lead:
        return None
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(lead, field, value)
    if payload.status in ("complete", "dead_end"):
        lead.completed_at = datetime.now(UTC)
    db.flush()
    db.refresh(lead)
    audit.log(
        db,
        action="updated",
        user_id=user_id,
        workspace_id=workspace_id,
        entity_type="lead",
        entity_id=lead.id,
    )
    return lead
