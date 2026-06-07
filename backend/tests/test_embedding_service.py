from unittest.mock import MagicMock, patch
import pytest


def test_is_available_false_without_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    from app.services import embedding_service
    embedding_service._openai_client = None
    assert embedding_service.is_available() is False


def test_is_available_true_with_key(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    from app.services import embedding_service
    assert embedding_service.is_available() is True


def test_embed_document_no_op_without_key(monkeypatch, db):
    """embed_document() does nothing when OPENAI_API_KEY is not set."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    from app.services import embedding_service
    embedding_service._openai_client = None
    # Should return without error even with a fake document_id
    embedding_service.embed_document("fake-doc-id", "fake-workspace-id", db)


def test_embed_document_stores_vector(monkeypatch, db, registered_user, auth_headers, client):
    """embed_document() stores a vector on the document when OpenAI is configured."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    fake_embedding = [0.1] * 1536

    mock_openai = MagicMock()
    mock_openai.embeddings.create.return_value = MagicMock(
        data=[MagicMock(embedding=fake_embedding)]
    )

    from app.models.document import Document
    from app.models.user import User
    import uuid

    # Look up the registered user's DB id
    user = db.query(User).filter(User.email == registered_user["email"]).first()

    # Create workspace and doc via API
    ws_resp = client.post(
        "/workspaces/",
        json={"name": "embed-test", "vertical": "general"},
        headers=auth_headers,
    )
    workspace_id = ws_resp.json()["id"]

    doc = Document(
        workspace_id=workspace_id,
        filename="embed_test.pdf",
        original_filename="embed_test.pdf",
        file_path="/tmp/embed_test.pdf",
        file_type="pdf",
        sha256_hash="embedhash" + str(uuid.uuid4()).replace("-", "")[:10],
        uploaded_by=user.id,
        detected_doc_type="DEED",
        extraction_status="complete",
    )
    db.add(doc)
    db.commit()

    from app.services import embedding_service
    embedding_service._openai_client = None

    with patch("app.services.embedding_service._get_openai_client", return_value=mock_openai):
        embedding_service.embed_document(doc.id, workspace_id, db)

    db.refresh(doc)
    assert doc.embedding is not None
