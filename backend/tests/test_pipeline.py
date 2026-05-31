"""
Pipeline and extraction engine tests.

All Claude calls are mocked via `patch("app.services.claude_client.get_client")`.
_run_pipeline is called directly (not through the HTTP router) so we can
inspect DB state after each step without fighting background-task timing.
"""
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.models.document import Document
from app.models.document_extraction import DocumentExtraction
from app.models.document_schema import DocumentSchema
from app.models.user import User
from app.models.workspace import Workspace
from app.services.extraction_evaluator import EvaluationResult, evaluate


# ── Evaluator unit tests ─────────────────────────────────────────────────────

def test_evaluate_returns_no_review_when_all_confident():
    extractions = [
        {"field_name": "grantor_name", "confidence": 0.95},
        {"field_name": "sale_price", "confidence": 0.90},
    ]
    result = evaluate(extractions, threshold=0.75)
    assert isinstance(result, EvaluationResult)
    assert result.needs_review is False
    assert result.low_confidence_fields == []
    assert result.total_fields == 2


def test_evaluate_flags_fields_below_threshold():
    extractions = [
        {"field_name": "grantor_name", "confidence": 0.95},
        {"field_name": "sale_price", "confidence": 0.40},
        {"field_name": "parcel_id", "confidence": 0.30},
    ]
    result = evaluate(extractions, threshold=0.75)
    assert result.needs_review is True
    assert "sale_price" in result.low_confidence_fields
    assert "parcel_id" in result.low_confidence_fields
    assert "grantor_name" not in result.low_confidence_fields
    assert result.total_fields == 3


def test_evaluate_empty_input_is_not_needs_review():
    # evaluate() is pure — empty list = no low-confidence fields = no review.
    # The pipeline (not the evaluator) is responsible for detecting API failure.
    result = evaluate([], threshold=0.75)
    assert result.needs_review is False
    assert result.total_fields == 0


# ── Shared fixtures ──────────────────────────────────────────────────────────

@pytest.fixture
def user(db):
    u = User(
        id=str(uuid.uuid4()),
        email=f"pipeline_{uuid.uuid4()}@test.com",
        full_name="Pipeline Tester",
        password_hash="x",
    )
    db.add(u)
    db.flush()
    return u


@pytest.fixture
def workspace(db, user):
    ws = Workspace(
        id=str(uuid.uuid4()),
        name="Pipeline Workspace",
        vertical="general",
        created_by=user.id,
    )
    db.add(ws)
    db.flush()
    return ws


@pytest.fixture
def deed_schema(db):
    schema = DocumentSchema(
        id=str(uuid.uuid4()),
        document_type="DEED",
        display_name="Deed",
        vertical="general",
        schema_fields=[
            {"name": "grantor_name", "type": "name", "description": "Name of grantor"},
            {"name": "sale_price", "type": "currency", "description": "Sale price in dollars"},
        ],
        extraction_prompt="Extract the following fields from this deed.",
        version=1,
        is_active=True,
        parse_strategy="claude",
        default_confidence_threshold=0.75,
    )
    db.add(schema)
    db.commit()
    return schema


@pytest.fixture
def pending_doc(db, workspace, user, tmp_path):
    file_path = tmp_path / "test.pdf"
    file_path.write_bytes(b"%PDF-1.4 Grantor: Jane Smith")
    doc = Document(
        id=str(uuid.uuid4()),
        workspace_id=workspace.id,
        filename="test.pdf",
        original_filename="test.pdf",
        file_path=str(file_path),
        file_type="pdf",
        sha256_hash="abc123",
        source_type="upload",
        uploaded_by=user.id,
        extraction_status="pending",
    )
    db.add(doc)
    db.commit()
    return doc


def _mock_claude_extraction(mock_client, extractions: list[dict]):
    """Configure mock_client to return a valid extraction response."""
    import json
    payload = json.dumps({"extractions": extractions})
    mock_client.messages.create.return_value = MagicMock(
        content=[MagicMock(text=payload)],
        usage=MagicMock(input_tokens=100, output_tokens=50),
    )


# ── Happy-path test ──────────────────────────────────────────────────────────

def test_pipeline_happy_path_marks_complete_with_extractions(
    db, workspace, user, deed_schema, pending_doc
):
    """End-to-end: mocked Claude returns real fields → doc is complete, rows saved."""
    from app.services.document_pipeline import _run_pipeline

    mock_client = MagicMock()
    _mock_claude_extraction(mock_client, [
        {"field_name": "grantor_name", "field_value": "Jane Smith", "field_type": "name", "confidence": 0.95},
        {"field_name": "sale_price", "field_value": "285000", "field_type": "currency", "confidence": 0.88},
    ])
    with patch("app.services.document_pipeline.detect_document_type", return_value="DEED"), \
         patch("app.services.document_pipeline.extract_text", return_value="Grantor: Jane Smith"), \
         patch("app.services.document_pipeline.generate_standardized_name", return_value="deed.pdf"), \
         patch("app.services.claude_client.get_client", return_value=mock_client):

        _run_pipeline(
            pending_doc.id, b"%PDF-1.4 content", "test.pdf",
            workspace.id, user.id, db,
        )

    db.refresh(pending_doc)
    assert pending_doc.extraction_status == "complete"

    rows = db.query(DocumentExtraction).filter(
        DocumentExtraction.document_id == pending_doc.id
    ).all()
    assert len(rows) == 2
    names = {r.field_name for r in rows}
    assert "grantor_name" in names
    assert "sale_price" in names


# ── C2: false-complete on extraction failure ─────────────────────────────────

def test_pipeline_marks_failed_when_all_claude_batches_raise(
    db, workspace, user, deed_schema, pending_doc
):
    """C2: API outage → all batches fail → doc must be 'failed', not 'complete'."""
    from app.services.document_pipeline import _run_pipeline

    mock_client = MagicMock()
    mock_client.messages.create.side_effect = Exception("Claude API is unavailable")
    with patch("app.services.document_pipeline.detect_document_type", return_value="DEED"), \
         patch("app.services.document_pipeline.extract_text", return_value="some deed text"), \
         patch("app.services.document_pipeline.generate_standardized_name", return_value="deed.pdf"), \
         patch("app.services.claude_client.get_client", return_value=mock_client):

        _run_pipeline(
            pending_doc.id, b"%PDF-1.4 content", "test.pdf",
            workspace.id, user.id, db,
        )

    db.refresh(pending_doc)
    assert pending_doc.extraction_status == "failed", (
        f"Expected 'failed' but got '{pending_doc.extraction_status}' — "
        "C2 bug: API failure silently reports complete"
    )
    assert pending_doc.extraction_error is not None

    rows = db.query(DocumentExtraction).filter(
        DocumentExtraction.document_id == pending_doc.id
    ).all()
    assert len(rows) == 0, "No extraction rows should exist when API failed"


def test_pipeline_marks_complete_when_schema_has_no_fields(
    db, workspace, user, tmp_path
):
    """Edge case: zero-field claude schema → complete is correct (no batches run)."""
    from app.services.document_pipeline import _run_pipeline

    schema = DocumentSchema(
        id=str(uuid.uuid4()),
        document_type="ZERO-FIELD",
        display_name="Zero Field",
        vertical="general",
        schema_fields=[],
        version=1,
        is_active=True,
        parse_strategy="claude",
        default_confidence_threshold=0.75,
    )
    db.add(schema)
    file_path = tmp_path / "zf.pdf"
    file_path.write_bytes(b"%PDF-1.4 x")
    doc = Document(
        id=str(uuid.uuid4()),
        workspace_id=workspace.id,
        filename="zf.pdf",
        original_filename="zf.pdf",
        file_path=str(file_path),
        file_type="pdf",
        sha256_hash="zf123",
        source_type="upload",
        uploaded_by=user.id,
        extraction_status="pending",
    )
    db.add(doc)
    db.commit()

    with patch("app.services.document_pipeline.detect_document_type", return_value="ZERO-FIELD"), \
         patch("app.services.document_pipeline.extract_text", return_value="content"), \
         patch("app.services.document_pipeline.generate_standardized_name", return_value="zf.pdf"), \
         patch("app.services.claude_client.get_client", return_value=MagicMock()):  # no calls expected

        _run_pipeline(doc.id, b"%PDF-1.4 x", "zf.pdf", workspace.id, user.id, db)

    db.refresh(doc)
    assert doc.extraction_status == "complete"


# ── H5: 4000-char text cap ────────────────────────────────────────────────────

def test_extraction_sends_full_text_beyond_4000_chars(db, deed_schema):
    """H5: Claude must receive OCR text that extends past the old 4000-char cap."""
    from app.services.extraction_engine import extract_fields

    # Build text where a critical value appears at position 5000
    padding = "A" * 4500
    long_ocr = f"{padding} GRANTOR_EVIDENCE_AT_5000"
    assert len(long_ocr) > 4000

    captured_prompts = []

    def capture_call(**kwargs):
        msg = kwargs.get("messages", [{}])[0].get("content", "")
        captured_prompts.append(msg)
        return MagicMock(
            content=[MagicMock(text='{"extractions": []}')],
            usage=MagicMock(input_tokens=10, output_tokens=5),
        )

    mock_client = MagicMock()
    mock_client.messages.create.side_effect = capture_call
    with patch("app.services.claude_client.get_client", return_value=mock_client):
        extract_fields(long_ocr, deed_schema)

    assert captured_prompts, "Expected at least one Claude call"
    assert "GRANTOR_EVIDENCE_AT_5000" in captured_prompts[0], (
        "Text beyond 4000 chars was not sent to Claude — H5 truncation bug still present"
    )


# ── L3: orphaned file cleanup ─────────────────────────────────────────────────

def test_pipeline_deletes_file_on_ocr_failure(db, workspace, user, deed_schema, tmp_path):
    """L3: a file written to disk before OCR must be deleted when the pipeline fails."""
    from app.services.document_pipeline import _run_pipeline

    file_path = tmp_path / "orphan.pdf"
    file_path.write_bytes(b"%PDF-1.4 x")
    doc = Document(
        id=str(uuid.uuid4()),
        workspace_id=workspace.id,
        filename="orphan.pdf",
        original_filename="orphan.pdf",
        file_path=str(file_path),
        file_type="pdf",
        sha256_hash="orph123",
        source_type="upload",
        uploaded_by=user.id,
        extraction_status="pending",
    )
    db.add(doc)
    db.commit()

    assert file_path.exists(), "File must exist before pipeline runs"

    with patch("app.services.document_pipeline.extract_text", side_effect=Exception("OCR failed")):
        _run_pipeline(doc.id, b"%PDF-1.4 x", "orphan.pdf", workspace.id, user.id, db)

    db.refresh(doc)
    assert doc.extraction_status == "failed"
    assert not file_path.exists(), (
        "L3: orphaned file still on disk after pipeline failure"
    )


def test_pipeline_preserves_file_on_success(db, workspace, user, deed_schema, pending_doc):
    """Sanity: successful pipeline must NOT delete the stored file."""
    from app.services.document_pipeline import _run_pipeline

    file_path = Path(pending_doc.file_path)
    assert file_path.exists()

    mock_client = MagicMock()
    _mock_claude_extraction(mock_client, [
        {"field_name": "grantor_name", "field_value": "Jane Smith", "field_type": "name", "confidence": 0.95},
    ])
    with patch("app.services.document_pipeline.detect_document_type", return_value="DEED"), \
         patch("app.services.document_pipeline.extract_text", return_value="deed content"), \
         patch("app.services.document_pipeline.generate_standardized_name", return_value="deed.pdf"), \
         patch("app.services.claude_client.get_client", return_value=mock_client):

        _run_pipeline(pending_doc.id, b"%PDF-1.4 x", "test.pdf", workspace.id, user.id, db)

    db.refresh(pending_doc)
    assert pending_doc.extraction_status == "complete"
    assert file_path.exists(), "Successful pipeline must not delete the stored file"


# ── Dual confidence ───────────────────────────────────────────────────────────

def test_extract_batch_returns_ocr_confidence(db, deed_schema):
    """_extract_batch must include ocr_confidence in each returned dict."""
    from app.services.extraction_engine import _extract_batch
    import json

    mock_client = MagicMock()
    payload = json.dumps({"extractions": [
        {
            "field_name": "grantor_name",
            "field_value": "Jane Smith",
            "field_type": "name",
            "confidence": 0.92,
            "ocr_confidence": 0.85,
        }
    ]})
    mock_client.messages.create.return_value = MagicMock(
        content=[MagicMock(text=payload)],
        usage=MagicMock(input_tokens=100, output_tokens=50),
    )

    with patch("app.services.claude_client.get_client", return_value=mock_client):
        results = _extract_batch(
            ocr_text="Grantor: Jane Smith",
            fields_batch=[{"name": "grantor_name", "type": "name", "description": "Grantor name"}],
            schema=deed_schema,
        )

    assert len(results) == 1
    assert "ocr_confidence" in results[0]
    assert results[0]["ocr_confidence"] == 0.85


def test_extract_batch_falls_back_ocr_confidence_to_confidence(db, deed_schema):
    """If Claude omits ocr_confidence, it defaults to the ai confidence value."""
    from app.services.extraction_engine import _extract_batch
    import json

    mock_client = MagicMock()
    payload = json.dumps({"extractions": [
        {
            "field_name": "grantor_name",
            "field_value": "Jane Smith",
            "field_type": "name",
            "confidence": 0.80,
            # ocr_confidence intentionally absent
        }
    ]})
    mock_client.messages.create.return_value = MagicMock(
        content=[MagicMock(text=payload)],
        usage=MagicMock(input_tokens=100, output_tokens=50),
    )

    with patch("app.services.claude_client.get_client", return_value=mock_client):
        results = _extract_batch(
            ocr_text="Grantor: Jane Smith",
            fields_batch=[{"name": "grantor_name", "type": "name", "description": "Grantor name"}],
            schema=deed_schema,
        )

    assert results[0]["ocr_confidence"] == 0.80


def test_evaluate_uses_per_field_ai_threshold_correct():
    """When a field has ai_threshold in schema_fields, use it instead of the default."""
    extractions = [
        {"field_name": "ein", "confidence": 0.88, "ocr_confidence": 0.95},
        {"field_name": "vendor_name", "confidence": 0.80, "ocr_confidence": 0.90},
    ]
    result = evaluate(
        extractions,
        threshold=0.75,
        field_thresholds={"ein": 0.95},
    )
    assert "ein" in result.low_confidence_fields       # 0.88 < 0.95 (field threshold)
    assert "vendor_name" not in result.low_confidence_fields  # 0.80 >= 0.75 (default)


def test_evaluate_flags_low_ocr_confidence():
    """Fields below the ocr_threshold are flagged even when ai confidence is high."""
    extractions = [
        {"field_name": "sale_price", "confidence": 0.90, "ocr_confidence": 0.50},
    ]
    result = evaluate(
        extractions,
        threshold=0.75,
        ocr_threshold=0.70,
    )
    assert "sale_price" in result.low_confidence_fields  # ocr 0.50 < ocr_threshold 0.70


def test_evaluate_passes_when_both_confidences_meet_thresholds():
    """Field passes only when both ai and ocr confidence are above their thresholds."""
    extractions = [
        {"field_name": "grantor_name", "confidence": 0.92, "ocr_confidence": 0.88},
    ]
    result = evaluate(
        extractions,
        threshold=0.75,
        ocr_threshold=0.80,
    )
    assert result.needs_review is False  # 0.92 >= 0.75 and 0.88 >= 0.80


# ── needs_review persistence (guard test) ────────────────────────────────────

def test_pipeline_marks_needs_review_when_required_field_missing(
    db, workspace, user, tmp_path
):
    """Required field missing from extraction → doc must be needs_review after pipeline completes."""
    from app.services.document_pipeline import _run_pipeline

    # Schema with a required field
    schema = DocumentSchema(
        id=str(uuid.uuid4()),
        document_type="REQUIRED-FIELD-TEST",
        display_name="Required Field Test",
        vertical="general",
        schema_fields=[{
            "name": "ein",
            "type": "id_number",
            "description": "EIN",
            "validation": {"required": True}
        }],
        extraction_prompt="Extract the EIN.",
        version=1,
        is_active=True,
        parse_strategy="claude",
        default_confidence_threshold=0.75,
    )
    db.add(schema)

    file_path = tmp_path / "test.pdf"
    file_path.write_bytes(b"%PDF-1.4 no ein here")
    doc = Document(
        id=str(uuid.uuid4()),
        workspace_id=workspace.id,
        filename="test.pdf",
        original_filename="test.pdf",
        file_path=str(file_path),
        file_type="pdf",
        sha256_hash="reqtest123",
        source_type="upload",
        uploaded_by=user.id,
        extraction_status="pending",
    )
    db.add(doc)
    db.commit()

    mock_client = MagicMock()
    # Claude returns a result but WITHOUT the required 'ein' field
    import json
    payload = json.dumps({"extractions": [
        {"field_name": "other_field", "field_value": "something", "field_type": "text",
         "confidence": 0.90, "ocr_confidence": 0.90}
    ]})
    mock_client.messages.create.return_value = MagicMock(
        content=[MagicMock(text=payload)],
        usage=MagicMock(input_tokens=100, output_tokens=50),
    )

    with patch("app.services.document_pipeline.detect_document_type", return_value="REQUIRED-FIELD-TEST"), \
         patch("app.services.document_pipeline.extract_text", return_value="no ein here"), \
         patch("app.services.document_pipeline.generate_standardized_name", return_value="test.pdf"), \
         patch("app.services.claude_client.get_client", return_value=mock_client):

        _run_pipeline(doc.id, b"%PDF-1.4 no ein here", "test.pdf", workspace.id, user.id, db)

    db.refresh(doc)
    assert doc.extraction_status == "needs_review", (
        f"Expected needs_review but got '{doc.extraction_status}' — "
        "required-field failure is being overwritten by the final complete assignment"
    )
    assert doc.extraction_error is not None
