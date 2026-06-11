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
    # WALKTHROUGH: notice how little is here — just INSERT a row. There is no
    # update() or delete() function in this module, and that's the whole point.
    # Immutability is NOT enforced in Python; it's enforced one layer down by a
    # Postgres trigger (alembic migration 3f29a7ad2392) that RAISEs an exception
    # on any UPDATE or DELETE against audit_log. Why push it to the database?
    # Because app-level rules can be bypassed — a future code path, a bug, a
    # rogue admin with a DB connection, or a compromised service could all issue
    # an UPDATE. The trigger catches every one of them: even raw SQL outside this
    # codebase cannot alter an audit row. For an evidence trail in a fraud
    # platform, "the app promises not to edit it" isn't good enough — the
    # database has to make editing impossible. This function only ever appends;
    # nothing, anywhere, can rewrite.
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
