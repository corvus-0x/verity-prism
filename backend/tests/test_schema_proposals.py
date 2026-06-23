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


from app.services.schema_proposal_service import validate_proposal


def _new_schema_proposal(**meta_over):
    meta = {"document_type": "PERMIT", "display_name": "Permit", "vertical": "general"}
    meta.update(meta_over)
    return SchemaChangeProposal(
        workspace_id="ws",
        proposal_type="new_schema",
        proposed_schema=meta,
        proposed_fields=[
            {"name": "permit_no", "type": "id_number", "description": "Permit number"}
        ],
    )


def test_validate_passes_clean_new_schema(db):
    assert validate_proposal(_new_schema_proposal(), db) == []


def test_validate_rejects_non_snake_case_field(db):
    p = _new_schema_proposal()
    p.proposed_fields = [{"name": "PermitNo", "type": "text", "description": "x"}]
    errors = validate_proposal(p, db)
    assert any("snake_case" in e for e in errors)


def test_validate_rejects_unknown_field_type(db):
    p = _new_schema_proposal()
    p.proposed_fields = [{"name": "permit_no", "type": "guid", "description": "x"}]
    errors = validate_proposal(p, db)
    assert any("field_type" in e for e in errors)


def test_validate_rejects_reserved_name(db):
    p = _new_schema_proposal()
    p.proposed_fields = [{"name": "document_id", "type": "text", "description": "x"}]
    errors = validate_proposal(p, db)
    assert any("reserved" in e for e in errors)


def test_validate_rejects_duplicate_field_names(db):
    p = _new_schema_proposal()
    p.proposed_fields = [
        {"name": "permit_no", "type": "text", "description": "a"},
        {"name": "permit_no", "type": "text", "description": "b"},
    ]
    errors = validate_proposal(p, db)
    assert any("duplicate" in e for e in errors)


def test_validate_rejects_threshold_out_of_range(db):
    p = _new_schema_proposal()
    p.proposed_fields = [
        {"name": "permit_no", "type": "text", "description": "x", "confidence_threshold": 1.5}
    ]
    errors = validate_proposal(p, db)
    assert any("threshold" in e for e in errors)


def test_validate_rejects_missing_description(db):
    p = _new_schema_proposal()
    p.proposed_fields = [{"name": "permit_no", "type": "text", "description": "  "}]
    errors = validate_proposal(p, db)
    assert any("description" in e for e in errors)


def test_validate_rejects_bad_document_type(db):
    errors = validate_proposal(_new_schema_proposal(document_type="permit record"), db)
    assert any("document_type" in e for e in errors)


def test_validate_rejects_collision_with_active_schema(db):
    db.add(
        DocumentSchema(
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
    )
    db.commit()
    errors = validate_proposal(_new_schema_proposal(), db)
    assert any("already" in e for e in errors)


def test_validate_extension_rejects_field_clashing_with_base(db):
    base = DocumentSchema(
        id=str(uuid.uuid4()),
        document_type="DEED",
        display_name="Deed",
        vertical="general",
        schema_fields=[{"name": "grantor_name", "type": "name", "description": "g"}],
        version=1,
        is_active=True,
        parse_strategy="claude",
        default_confidence_threshold=0.7,
    )
    db.add(base)
    db.commit()
    p = SchemaChangeProposal(
        workspace_id="ws",
        proposal_type="schema_extension",
        base_schema_id=base.id,
        proposed_schema={},
        proposed_fields=[
            {"name": "grantor_name", "type": "name", "description": "dup of base"},
        ],
    )
    errors = validate_proposal(p, db)
    assert any("duplicate" in e for e in errors)
