from sqlalchemy.orm import Session
from app.models.audit import AuditLog

def log(
    db: Session,
    action: str,
    user_id: str = None,
    workspace_id: str = None,
    entity_type: str = None,
    entity_id: str = None,
    before_state: dict = None,
    after_state: dict = None,
    ip_address: str = None,
):
    entry = AuditLog(
        action=action,
        user_id=user_id,
        workspace_id=workspace_id,
        entity_type=entity_type,
        entity_id=entity_id,
        before_state=before_state,
        after_state=after_state,
        ip_address=ip_address,
    )
    db.add(entry)
    db.commit()
