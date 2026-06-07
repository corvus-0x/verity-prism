import uuid
import pytest
from sqlalchemy import text
from sqlalchemy.exc import InternalError

from app.models.audit import AuditLog


def _make_entry(db):
    """Insert a single audit_log row and return it."""
    entry = AuditLog(
        id=str(uuid.uuid4()),
        action="test_event",
        entity_type="test",
        entity_id=str(uuid.uuid4()),
    )
    db.add(entry)
    db.commit()
    return entry


def test_insert_audit_log_succeeds(db):
    entry = _make_entry(db)
    assert entry.id is not None


def test_update_audit_log_is_blocked(db, test_engine):
    entry = _make_entry(db)
    with pytest.raises(InternalError):
        with test_engine.begin() as conn:
            conn.execute(
                text("UPDATE audit_log SET action = 'tampered' WHERE id = :id"),
                {"id": entry.id},
            )


def test_delete_audit_log_is_blocked(db, test_engine):
    entry = _make_entry(db)
    with pytest.raises(InternalError):
        with test_engine.begin() as conn:
            conn.execute(
                text("DELETE FROM audit_log WHERE id = :id"),
                {"id": entry.id},
            )
