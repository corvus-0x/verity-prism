"""Phase 1 — schema proposal backbone: model, uniqueness index, validation,
supersession, forced-schema reprocess."""

import uuid

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.document_schema import DocumentSchema
from app.models.schema_proposal import SchemaChangeProposal
from app.models.user import User
from app.models.workspace import Workspace


def _workspace(db, user) -> Workspace:
    ws = Workspace(id=str(uuid.uuid4()), name="WS", vertical="general", created_by=user.id)
    db.add(ws)
    db.flush()
    return ws


def _user(db) -> User:
    u = User(
        id=str(uuid.uuid4()),
        email=f"{uuid.uuid4()}@example.com",
        password_hash="x",
        full_name="T",
    )
    db.add(u)
    db.flush()
    return u


def test_proposal_persists_with_defaults(db):
    user = _user(db)
    ws = _workspace(db, user)
    p = SchemaChangeProposal(
        workspace_id=ws.id,
        proposal_type="new_schema",
        proposed_schema={"document_type": "PERMIT", "vertical": "general"},
        proposed_fields=[{"name": "permit_no", "type": "id_number", "description": "x"}],
        created_by_ai=True,
        model_id="claude-sonnet-4-6",
        prompt_version="schema_proposal_v1",
        proposer_inputs={"document_id": "abc", "ocr_chars": 1234},
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    assert p.id
    assert p.status == "draft"
    assert p.is_deleted is False
    assert p.proposer_inputs["ocr_chars"] == 1234


def test_db_rejects_second_active_schema_for_same_type_vertical(db):
    s1 = DocumentSchema(
        id=str(uuid.uuid4()),
        document_type="PERMIT",
        display_name="Permit",
        vertical="general",
        schema_fields=[],
        version=1,
        is_active=True,
        parse_strategy="claude",
        default_confidence_threshold=0.7,
    )
    db.add(s1)
    db.commit()
    s2 = DocumentSchema(
        id=str(uuid.uuid4()),
        document_type="PERMIT",
        display_name="Permit v2",
        vertical="general",
        schema_fields=[],
        version=2,
        is_active=True,
        parse_strategy="claude",
        default_confidence_threshold=0.7,
    )
    db.add(s2)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_db_allows_second_schema_when_first_is_inactive(db):
    s1 = DocumentSchema(
        id=str(uuid.uuid4()),
        document_type="PERMIT",
        display_name="Permit",
        vertical="general",
        schema_fields=[],
        version=1,
        is_active=False,
        parse_strategy="claude",
        default_confidence_threshold=0.7,
    )
    db.add(s1)
    db.commit()
    s2 = DocumentSchema(
        id=str(uuid.uuid4()),
        document_type="PERMIT",
        display_name="Permit v2",
        vertical="general",
        schema_fields=[],
        version=2,
        is_active=True,
        parse_strategy="claude",
        default_confidence_threshold=0.7,
    )
    db.add(s2)
    db.commit()  # must NOT raise
    db.refresh(s2)
    assert s2.is_active is True


def test_get_schema_for_type_prefers_active_highest_version(db):
    from app.services.extraction_engine import get_schema_for_type

    old = DocumentSchema(
        id=str(uuid.uuid4()),
        document_type="PERMIT",
        display_name="Permit",
        vertical="general",
        schema_fields=[],
        version=1,
        is_active=False,
        parse_strategy="claude",
        default_confidence_threshold=0.7,
    )
    new = DocumentSchema(
        id=str(uuid.uuid4()),
        document_type="PERMIT",
        display_name="Permit v2",
        vertical="general",
        schema_fields=[],
        version=2,
        is_active=True,
        parse_strategy="claude",
        default_confidence_threshold=0.7,
    )
    db.add_all([old, new])
    db.commit()
    result = get_schema_for_type("PERMIT", db, "general")
    assert result is not None
    assert result.id == new.id
    assert result.version == 2
