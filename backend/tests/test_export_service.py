import csv
import io
import json
import uuid

import pytest

from app.models.document import Document
from app.models.document_extraction import DocumentExtraction
from app.models.user import User
from app.models.workspace import Workspace
from app.services.export_service import (
    build_document_csv,
    build_document_json,
    build_workspace_csv,
    build_workspace_json,
    latest_extractions,
)


@pytest.fixture
def user(db):
    u = User(
        id=str(uuid.uuid4()),
        email=f"exp_{uuid.uuid4().hex[:8]}@test.com",
        password_hash="hashed",
        full_name="Export Test User",
    )
    db.add(u)
    db.commit()
    return u


@pytest.fixture
def workspace(db, user):
    ws = Workspace(id=str(uuid.uuid4()), name="Export WS", vertical="fraud", created_by=user.id)
    db.add(ws)
    db.commit()
    return ws


@pytest.fixture
def doc_with_extractions(db, workspace, user):
    doc = Document(
        id=str(uuid.uuid4()),
        workspace_id=workspace.id,
        filename="2024-01-15_DEED_smith_transfer.pdf",
        original_filename="deed.pdf",
        file_path="/uploads/deed.pdf",
        file_type="pdf",
        sha256_hash="a" * 64,
        uploaded_by=user.id,
        detected_doc_type="DEED",
        extraction_status="complete",
        is_deleted=False,
    )
    db.add(doc)
    db.commit()
    for attempt in (1, 2):
        db.add(DocumentExtraction(
            id=str(uuid.uuid4()),
            document_id=doc.id,
            workspace_id=workspace.id,
            field_name="grantor",
            field_value=f"John Smith attempt {attempt}",
            field_type="text",
            confidence=0.95,
            attempt=attempt,
        ))
    db.add(DocumentExtraction(
        id=str(uuid.uuid4()),
        document_id=doc.id,
        workspace_id=workspace.id,
        field_name="consideration_amount",
        field_value="250000",
        field_type="currency",
        confidence=0.9,
        attempt=1,
    ))
    db.commit()
    return doc


def test_latest_extractions_returns_only_latest_attempt(db, doc_with_extractions):
    exts = latest_extractions(doc_with_extractions.id, db)
    grantor_rows = [e for e in exts if e.field_name == "grantor"]
    assert len(grantor_rows) == 1
    assert grantor_rows[0].attempt == 2
    assert grantor_rows[0].field_value == "John Smith attempt 2"


def test_latest_extractions_returns_all_fields(db, doc_with_extractions):
    exts = latest_extractions(doc_with_extractions.id, db)
    field_names = {e.field_name for e in exts}
    assert field_names == {"grantor", "consideration_amount"}


def test_build_document_csv_contains_headers_and_data(db, doc_with_extractions):
    exts = latest_extractions(doc_with_extractions.id, db)
    content = build_document_csv(doc_with_extractions, exts)
    reader = csv.DictReader(io.StringIO(content))
    rows = list(reader)
    assert len(rows) == 2
    field_names = {r["field_name"] for r in rows}
    assert "grantor" in field_names
    assert "consideration_amount" in field_names


def test_build_document_csv_blocks_formula_injection(db, workspace, user):
    doc = Document(
        id=str(uuid.uuid4()),
        workspace_id=workspace.id,
        filename="malicious.pdf",
        original_filename="malicious.pdf",
        file_path="/uploads/malicious.pdf",
        file_type="pdf",
        sha256_hash="b" * 64,
        uploaded_by=user.id,
        detected_doc_type="DEED",
        extraction_status="complete",
        is_deleted=False,
    )
    db.add(doc)
    db.add(DocumentExtraction(
        id=str(uuid.uuid4()),
        document_id=doc.id,
        workspace_id=workspace.id,
        field_name="grantor",
        field_value="=CMD|'/c calc'!A0",
        field_type="text",
        confidence=0.95,
        attempt=1,
    ))
    db.commit()
    exts = latest_extractions(doc.id, db)
    content = build_document_csv(doc, exts)
    # escape_csv_cell prefixes formula-trigger values with ' (OWASP mitigation).
    # The cell is safe when it no longer starts with '=' — verify the real property.
    reader = csv.DictReader(io.StringIO(content))
    grantor_row = next(r for r in reader if r["field_name"] == "grantor")
    assert not grantor_row["field_value"].startswith("=")  # neutralized
    assert grantor_row["field_value"].startswith("'")       # prefixed by escape_csv_cell


def test_build_document_json_structure(db, doc_with_extractions):
    exts = latest_extractions(doc_with_extractions.id, db)
    content = build_document_json(doc_with_extractions, exts)
    data = json.loads(content)
    assert isinstance(data, list)
    assert len(data) == 2
    assert all("field_name" in row and "field_value" in row for row in data)


def test_build_workspace_csv_includes_all_docs(db, doc_with_extractions):
    docs = [doc_with_extractions]
    content = build_workspace_csv(docs, db)
    assert "2024-01-15_DEED_smith_transfer.pdf" in content
    assert "grantor" in content


def test_build_workspace_json_structure(db, doc_with_extractions):
    docs = [doc_with_extractions]
    content = build_workspace_json(docs, db)
    data = json.loads(content)
    assert isinstance(data, list)
    assert any(row["document_filename"] == "2024-01-15_DEED_smith_transfer.pdf" for row in data)
