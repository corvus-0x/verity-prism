"""
connector_service tests — ingest fetched bytes through the pipeline with
provenance + SHA-256 dedup.

process_upload_background is patched so no real pipeline (OCR/Claude/DB writes
beyond the pending Document) runs. user/workspace fixtures are defined locally
here (they live inside test_pipeline.py, not conftest.py).
"""
import uuid
from unittest.mock import patch

import pytest

from app.models.user import User
from app.models.workspace import Workspace
from app.services import connector_service
from app.services.connectors.base import FetchItemResult

# ── Local fixtures (mirror test_pipeline.py) ──────────────────────────────────

@pytest.fixture
def user(db):
    u = User(
        id=str(uuid.uuid4()),
        email=f"connector_{uuid.uuid4()}@test.com",
        full_name="Connector Tester",
        password_hash="x",
    )
    db.add(u)
    db.flush()
    return u


@pytest.fixture
def workspace(db, user):
    ws = Workspace(
        id=str(uuid.uuid4()),
        name="Connector Workspace",
        vertical="general",
        created_by=user.id,
    )
    db.add(ws)
    db.flush()
    return ws


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_ingest_bytes_creates_document_with_provenance(db, workspace, user):
    with patch("app.services.document_pipeline.process_upload_background"):
        outcome = connector_service.ingest_bytes(
            db=db, workspace_id=workspace.id, user_id=user.id,
            filename="2023_123456789_990.xml", file_bytes=b"<Return>x</Return>",
            connector_id="irs-teos", item_ref="123456789:2023:obj",
        )
    assert isinstance(outcome, FetchItemResult)
    assert outcome.status == "created"
    assert outcome.document_id is not None


def test_ingest_bytes_skips_duplicate_by_hash(db, workspace, user):
    payload = b"<Return>same</Return>"
    with patch("app.services.document_pipeline.process_upload_background"):
        first = connector_service.ingest_bytes(
            db=db, workspace_id=workspace.id, user_id=user.id,
            filename="a.xml", file_bytes=payload, connector_id="irs-teos", item_ref="r1",
        )
        second = connector_service.ingest_bytes(
            db=db, workspace_id=workspace.id, user_id=user.id,
            filename="b.xml", file_bytes=payload, connector_id="irs-teos", item_ref="r2",
        )
    assert first.status == "created"
    assert second.status == "skipped"
    assert "already in workspace" in (second.reason or "")
    assert second.document_id == first.document_id
