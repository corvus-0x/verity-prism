from sqlalchemy.orm import Session

from app.models.finding import Finding, SignalType
from app.schemas.finding import FindingCreate, FindingUpdate
from app.services import audit

SIGNAL_TYPES_SEED = [
    {
        "code": "SR-003",
        "name": "VALUATION_ANOMALY",
        "description": "Property purchased significantly above or below appraised value",
        "severity": "critical",
        "relevant_to": ["AG", "IRS"],
    },
    {
        "code": "SR-004",
        "name": "UCC_BURST",
        "description": "Multiple UCC amendments filed within minutes — coordinated lien activity",
        "severity": "high",
        "relevant_to": ["FCA", "FBI"],
    },
    {
        "code": "SR-005",
        "name": "ZERO_CONSIDERATION",
        "description": "Property transferred for $0 to a private party",
        "severity": "critical",
        "relevant_to": ["AG", "IRS"],
    },
    {
        "code": "SR-015",
        "name": "DEED_TITLE_DEFECT",
        "description": "Deed executed in favor of an entity that did not legally exist at the time",
        "severity": "high",
        "relevant_to": ["AG"],
    },
    {
        "code": "SR-021",
        "name": "REVENUE_SPIKE",
        "description": "Organization revenue increased more than 500% year-over-year",
        "severity": "medium",
        "relevant_to": ["IRS"],
    },
    {
        "code": "SR-024",
        "name": "CHARITY_CONDUIT",
        "description": "Charitable funds used to fund improvements on privately-owned property",
        "severity": "critical",
        "relevant_to": ["IRS", "AG", "FBI"],
    },
    {
        "code": "SR-025",
        "name": "FALSE_DISCLOSURE",
        "description": "Organization disclosed related-party transactions in one year then denied them in all subsequent years while transactions continued",
        "severity": "critical",
        "relevant_to": ["IRS", "AG"],
    },
    {
        "code": "SR-026",
        "name": "CONSTRUCTION_OVERAGE",
        "description": "Construction permit value exceeds total organization revenue for that period",
        "severity": "high",
        "relevant_to": ["IRS", "AG"],
    },
]


def seed_signal_types(db: Session) -> None:
    """Idempotently seed the signal-type reference table on first read."""
    if db.query(SignalType).count() == 0:
        for s in SIGNAL_TYPES_SEED:
            db.add(SignalType(**s))
        db.commit()


def list_signal_types(db: Session) -> list[SignalType]:
    """List all signal types, seeding the reference table if empty."""
    seed_signal_types(db)
    return db.query(SignalType).all()


def create_finding(db: Session, workspace_id: str, user_id: str, payload: FindingCreate) -> Finding:
    """Create a finding and write an audit entry."""
    finding = Finding(**payload.model_dump(), workspace_id=workspace_id, created_by=user_id)
    db.add(finding)
    db.commit()
    db.refresh(finding)
    audit.log(
        db,
        action="created",
        user_id=user_id,
        workspace_id=workspace_id,
        entity_type="finding",
        entity_id=finding.id,
        after_state={"title": finding.title, "severity": finding.severity},
    )
    return finding


def list_findings(db: Session, workspace_id: str) -> list[Finding]:
    """List active (non-deleted) findings in a workspace."""
    return (
        db.query(Finding)
        .filter(
            Finding.workspace_id == workspace_id,
            Finding.is_deleted == False,  # noqa: E712
        )
        .all()
    )


def update_finding(
    db: Session, workspace_id: str, finding_id: str, user_id: str, payload: FindingUpdate
) -> Finding | None:
    """Apply a partial update to a finding; return None if not found."""
    finding = (
        db.query(Finding)
        .filter(
            Finding.id == finding_id,
            Finding.workspace_id == workspace_id,
        )
        .first()
    )
    if not finding:
        return None
    before = {"status": finding.status}
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(finding, field, value)
    db.commit()
    db.refresh(finding)
    audit.log(
        db,
        action="updated",
        user_id=user_id,
        workspace_id=workspace_id,
        entity_type="finding",
        entity_id=finding.id,
        before_state=before,
        after_state={"status": finding.status},
    )
    return finding
