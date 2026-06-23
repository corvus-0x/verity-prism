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
    assert any("already exists in the base schema" in e for e in errors)


from unittest.mock import patch

from app.models.document import Document
from app.models.document_extraction import DocumentExtraction
from app.services import document_service


def _doc_with_ocr(db, ws, user, schema_id=None, status="no_schema", ocr="Permit No 12345"):
    doc = Document(
        id=str(uuid.uuid4()),
        workspace_id=ws.id,
        filename="permit.pdf",
        original_filename="permit.pdf",
        file_path="/tmp/permit.pdf",
        file_type="pdf",
        sha256_hash=str(uuid.uuid4()),
        uploaded_by=user.id,
        extraction_status=status,
        schema_id=schema_id,
        ocr_text=ocr,
    )
    db.add(doc)
    db.commit()
    return doc


def test_reprocess_document_forces_schema_without_detection(db):
    user = _user(db)
    ws = _workspace(db, user)
    schema = DocumentSchema(
        id=str(uuid.uuid4()),
        document_type="PERMIT",
        display_name="Permit",
        vertical="general",
        schema_fields=[{"name": "permit_no", "type": "id_number", "description": "Permit number"}],
        version=1,
        is_active=True,
        parse_strategy="claude",
        default_confidence_threshold=0.7,
    )
    db.add(schema)
    db.commit()
    doc = _doc_with_ocr(db, ws, user)

    fake_rows = [
        {
            "field_name": "permit_no",
            "field_value": "12345",
            "field_type": "id_number",
            "confidence": 0.95,
            "ocr_confidence": 0.95,
        }
    ]
    # detect_document_type must NOT be called; extract_fields is forced on the given schema.
    # Patch at the SOURCE module (extraction_engine) — reprocess_document never imports
    # detect_document_type, so there is no name to patch on document_service, and the ruff
    # --fix hook would strip any unused import anyway.
    with (
        patch("app.services.extraction_engine.detect_document_type") as detect,
        patch("app.services.document_service.extract_fields", return_value=fake_rows),
    ):
        result = document_service.reprocess_document(doc.id, schema.id, db)

    detect.assert_not_called()
    db.refresh(result)
    assert result.schema_id == schema.id
    assert result.detected_doc_type == "PERMIT"
    assert result.extraction_status == "complete"
    rows = db.query(DocumentExtraction).filter(DocumentExtraction.document_id == doc.id).all()
    assert len(rows) == 1
    assert rows[0].field_name == "permit_no"
    assert rows[0].field_value == "12345"


def test_reprocess_document_clears_prior_extractions(db):
    user = _user(db)
    ws = _workspace(db, user)
    schema = DocumentSchema(
        id=str(uuid.uuid4()),
        document_type="PERMIT",
        display_name="Permit",
        vertical="general",
        schema_fields=[{"name": "permit_no", "type": "id_number", "description": "Permit number"}],
        version=1,
        is_active=True,
        parse_strategy="claude",
        default_confidence_threshold=0.7,
    )
    db.add(schema)
    db.commit()
    doc = _doc_with_ocr(db, ws, user, schema_id=schema.id, status="complete")
    db.add(
        DocumentExtraction(
            id=str(uuid.uuid4()),
            document_id=doc.id,
            workspace_id=ws.id,
            field_name="stale_field",
            field_value="old",
            field_type="text",
            confidence=0.5,
            schema_id=schema.id,
            attempt=1,
        )
    )
    db.commit()

    fake_rows = [
        {
            "field_name": "permit_no",
            "field_value": "999",
            "field_type": "id_number",
            "confidence": 0.9,
            "ocr_confidence": 0.9,
        }
    ]
    with patch("app.services.document_service.extract_fields", return_value=fake_rows):
        document_service.reprocess_document(doc.id, schema.id, db)

    names = [
        r.field_name
        for r in db.query(DocumentExtraction).filter(DocumentExtraction.document_id == doc.id).all()
    ]
    assert "stale_field" not in names
    assert "permit_no" in names


def test_reprocess_document_requires_ocr_text(db):
    user = _user(db)
    ws = _workspace(db, user)
    schema = DocumentSchema(
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
    db.add(schema)
    db.commit()
    doc = _doc_with_ocr(db, ws, user, ocr=None)
    with pytest.raises(ValueError, match="ocr_text"):
        document_service.reprocess_document(doc.id, schema.id, db)


from app.services.schema_proposal_service import supersede_schema


def test_supersede_schema_swaps_active_version_atomically(db):
    base = DocumentSchema(
        id=str(uuid.uuid4()),
        document_type="DEED",
        display_name="Deed",
        vertical="general",
        schema_fields=[{"name": "grantor_name", "type": "name", "description": "g"}],
        version=1,
        is_active=True,
        parse_strategy="claude",
        default_confidence_threshold=0.75,
    )
    db.add(base)
    db.commit()

    new_fields = base.schema_fields + [
        {"name": "notary_commission_expiration", "type": "date", "description": "Notary expiry"}
    ]
    new_schema = supersede_schema(db, base, new_fields)
    db.refresh(base)

    assert base.is_active is False
    assert new_schema.is_active is True
    assert new_schema.version == 2
    assert new_schema.document_type == "DEED"
    assert new_schema.vertical == "general"
    assert new_schema.parse_strategy == "claude"
    assert new_schema.default_confidence_threshold == 0.75
    assert len(new_schema.schema_fields) == 2
    # invariant intact: exactly one active DEED/general schema
    active = (
        db.query(DocumentSchema)
        .filter(
            DocumentSchema.document_type == "DEED",
            DocumentSchema.vertical == "general",
            DocumentSchema.is_active == True,  # noqa: E712
        )
        .all()
    )
    assert len(active) == 1
    assert active[0].id == new_schema.id


# ── Review-hardening tests (PR #13 review findings) ──────────────────────────


def test_validate_rejects_empty_fields(db):
    p = _new_schema_proposal()
    p.proposed_fields = []
    errors = validate_proposal(p, db)
    assert any("at least one field" in e for e in errors)


def test_validate_rejects_missing_display_name(db):
    errors = validate_proposal(_new_schema_proposal(display_name=""), db)
    assert any("display_name" in e for e in errors)


def test_validate_rejects_field_with_null_name(db):
    p = _new_schema_proposal()
    p.proposed_fields = [{"name": None, "type": "text", "description": "x"}]
    errors = validate_proposal(p, db)
    assert any("missing or empty name" in e for e in errors)


def test_validate_rejects_trailing_or_double_underscore_name(db):
    p = _new_schema_proposal()
    p.proposed_fields = [{"name": "bad__name_", "type": "text", "description": "x"}]
    errors = validate_proposal(p, db)
    assert any("snake_case" in e for e in errors)


def test_validate_rejects_non_dict_field_entry(db):
    p = _new_schema_proposal()
    p.proposed_fields = ["not_a_dict", 42]
    errors = validate_proposal(p, db)
    assert any("must be an object" in e for e in errors)


def test_validate_extension_requires_base_schema_id(db):
    p = SchemaChangeProposal(
        workspace_id="ws",
        proposal_type="schema_extension",
        base_schema_id=None,
        proposed_schema={},
        proposed_fields=[{"name": "x", "type": "text", "description": "y"}],
    )
    errors = validate_proposal(p, db)
    assert any("base_schema_id" in e for e in errors)


def test_validate_extension_rejects_nonexistent_base_schema(db):
    p = SchemaChangeProposal(
        workspace_id="ws",
        proposal_type="schema_extension",
        base_schema_id="does-not-exist",
        proposed_schema={},
        proposed_fields=[{"name": "x", "type": "text", "description": "y"}],
    )
    errors = validate_proposal(p, db)
    assert any("not found" in e for e in errors)


def test_reprocess_document_zero_rows_marks_needs_review(db):
    user = _user(db)
    ws = _workspace(db, user)
    schema = DocumentSchema(
        id=str(uuid.uuid4()),
        document_type="PERMIT",
        display_name="Permit",
        vertical="general",
        schema_fields=[{"name": "permit_no", "type": "id_number", "description": "Permit number"}],
        version=1,
        is_active=True,
        parse_strategy="claude",
        default_confidence_threshold=0.7,
    )
    db.add(schema)
    db.commit()
    doc = _doc_with_ocr(db, ws, user)
    with patch("app.services.document_service.extract_fields", return_value=[]):
        result = document_service.reprocess_document(doc.id, schema.id, db)
    db.refresh(result)
    assert result.extraction_status == "needs_review"
    assert result.extraction_error == "Reprocess returned zero fields"


def test_reprocess_document_marks_failed_on_extraction_error(db):
    from app.services.extraction_engine import ExtractionBatchError

    user = _user(db)
    ws = _workspace(db, user)
    schema = DocumentSchema(
        id=str(uuid.uuid4()),
        document_type="PERMIT",
        display_name="Permit",
        vertical="general",
        schema_fields=[{"name": "permit_no", "type": "id_number", "description": "Permit number"}],
        version=1,
        is_active=True,
        parse_strategy="claude",
        default_confidence_threshold=0.7,
    )
    db.add(schema)
    db.commit()
    doc = _doc_with_ocr(db, ws, user)
    with patch(
        "app.services.document_service.extract_fields",
        side_effect=ExtractionBatchError("api down"),
    ):
        with pytest.raises(ExtractionBatchError):
            document_service.reprocess_document(doc.id, schema.id, db)
    db.expire_all()
    reloaded = db.query(Document).filter(Document.id == doc.id).first()
    assert reloaded.extraction_status == "failed"
    assert "api down" in (reloaded.extraction_error or "")


def test_reprocess_document_preserves_prior_extractions_on_failure(db):
    """A failed reprocess must NOT destroy the document's prior evidence rows."""
    from app.services.extraction_engine import ExtractionBatchError

    user = _user(db)
    ws = _workspace(db, user)
    schema = DocumentSchema(
        id=str(uuid.uuid4()),
        document_type="PERMIT",
        display_name="Permit",
        vertical="general",
        schema_fields=[{"name": "permit_no", "type": "id_number", "description": "Permit number"}],
        version=1,
        is_active=True,
        parse_strategy="claude",
        default_confidence_threshold=0.7,
    )
    db.add(schema)
    db.commit()
    doc = _doc_with_ocr(db, ws, user, schema_id=schema.id, status="complete")
    db.add(
        DocumentExtraction(
            id=str(uuid.uuid4()),
            document_id=doc.id,
            workspace_id=ws.id,
            field_name="prior_field",
            field_value="keep me",
            field_type="text",
            confidence=0.9,
            schema_id=schema.id,
            attempt=1,
        )
    )
    db.commit()

    with patch(
        "app.services.document_service.extract_fields",
        side_effect=ExtractionBatchError("api down"),
    ):
        with pytest.raises(ExtractionBatchError):
            document_service.reprocess_document(doc.id, schema.id, db)

    db.expire_all()
    surviving = [
        r.field_name
        for r in db.query(DocumentExtraction).filter(DocumentExtraction.document_id == doc.id).all()
    ]
    assert surviving == ["prior_field"]  # prior evidence intact
    reloaded = db.query(Document).filter(Document.id == doc.id).first()
    assert reloaded.extraction_status == "failed"


def test_supersede_schema_writes_audit_row(db):
    from app.models.audit import AuditLog

    actor = _user(db)  # audit_log.user_id is a FK to users — use a real id
    db.commit()
    base = DocumentSchema(
        id=str(uuid.uuid4()),
        document_type="DEED",
        display_name="Deed",
        vertical="general",
        schema_fields=[],
        version=1,
        is_active=True,
        parse_strategy="claude",
        default_confidence_threshold=0.75,
    )
    db.add(base)
    db.commit()
    base_id = base.id
    supersede_schema(
        db, base, [{"name": "x", "type": "text", "description": "y"}], actor_id=actor.id
    )
    row = db.query(AuditLog).filter(AuditLog.action == "schema_superseded").first()
    assert row is not None
    assert row.user_id == actor.id
    assert row.before_state["id"] == base_id


def test_vertical_specific_schema_preferred_over_general(db):
    """When both a vertical-specific and a general schema exist for one doc_type,
    a workspace in that vertical gets the vertical-specific schema."""
    from app.services.extraction_engine import get_schema_for_type

    general = DocumentSchema(
        id=str(uuid.uuid4()),
        document_type="DEED",
        display_name="Deed (general)",
        vertical="general",
        schema_fields=[],
        version=1,
        is_active=True,
        parse_strategy="claude",
        default_confidence_threshold=0.7,
    )
    fraud_specific = DocumentSchema(
        id=str(uuid.uuid4()),
        document_type="DEED",
        display_name="Deed (fraud)",
        vertical="fraud",
        schema_fields=[],
        version=1,
        is_active=True,
        parse_strategy="claude",
        default_confidence_threshold=0.7,
    )
    db.add_all([general, fraud_specific])
    db.commit()
    result = get_schema_for_type("DEED", db, workspace_vertical="fraud")
    assert result is not None
    assert result.vertical == "fraud"


def test_reprocess_document_skips_soft_deleted(db):
    user = _user(db)
    ws = _workspace(db, user)
    schema = DocumentSchema(
        id=str(uuid.uuid4()),
        document_type="PERMIT",
        display_name="Permit",
        vertical="general",
        schema_fields=[{"name": "permit_no", "type": "id_number", "description": "Permit number"}],
        version=1,
        is_active=True,
        parse_strategy="claude",
        default_confidence_threshold=0.7,
    )
    db.add(schema)
    db.commit()
    doc = _doc_with_ocr(db, ws, user)
    doc.is_deleted = True
    db.commit()
    with pytest.raises(ValueError, match="not found"):
        document_service.reprocess_document(doc.id, schema.id, db)
