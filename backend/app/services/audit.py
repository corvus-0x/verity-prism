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
    """Write an immutable audit entry.

    The audit_log table has a PostgreSQL trigger that blocks UPDATE and DELETE,
    so every call here is a permanent record. Call this from services after every
    meaningful action — create, update, soft-delete, login, etc.

    before_state / after_state accept any dict; store the relevant fields, not
    entire ORM objects.
    """
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
