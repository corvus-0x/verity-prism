from sqlalchemy.orm import Session

from app.models.finding import Finding, SignalType
from app.schemas.finding import FindingCreate, FindingUpdate
from app.services import audit


def list_signal_types(db: Session) -> list[SignalType]:
    """List all signal types. The catalog is reference data seeded by an Alembic
    migration (f2b3c4d5e6f7), so this is a plain read with no on-demand seeding."""
    return db.query(SignalType).all()


def create_finding(db: Session, workspace_id: str, user_id: str, payload: FindingCreate) -> Finding:
    """Create a finding and write an audit entry."""
    finding = Finding(**payload.model_dump(), workspace_id=workspace_id, created_by=user_id)
    db.add(finding)
    db.flush()
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
            Finding.is_deleted == False,  # noqa: E712
        )
        .first()
    )
    if not finding:
        return None
    before = {"status": finding.status}
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(finding, field, value)
    db.flush()
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
