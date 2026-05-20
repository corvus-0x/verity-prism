import io
import pytest
from unittest.mock import patch, MagicMock


@pytest.fixture
def workspace_id(client, auth_headers):
    return client.post("/workspaces/", json={"name": "Test"},
                       headers=auth_headers).json()["id"]


def test_upload_creates_document_record(client, auth_headers, workspace_id):
    content = b"%PDF-1.4 test content"
    response = client.post(
        f"/workspaces/{workspace_id}/documents",
        files={"file": ("test_deed.pdf", io.BytesIO(content), "application/pdf")},
        headers=auth_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["original_filename"] == "test_deed.pdf"
    assert len(data["sha256_hash"]) == 64
    assert data["extraction_status"] in ("pending", "complete", "failed", "no_schema")


def test_original_filename_is_preserved(client, auth_headers, workspace_id):
    content = b"some content"
    response = client.post(
        f"/workspaces/{workspace_id}/documents",
        files={"file": ("My Weird File Name (copy).pdf", io.BytesIO(content), "application/pdf")},
        headers=auth_headers,
    )
    assert response.status_code == 201
    assert response.json()["original_filename"] == "My Weird File Name (copy).pdf"


def test_same_content_produces_same_hash(client, auth_headers, workspace_id):
    content = b"identical file content"
    r1 = client.post(f"/workspaces/{workspace_id}/documents",
                     files={"file": ("a.pdf", io.BytesIO(content), "application/pdf")},
                     headers=auth_headers)
    r2 = client.post(f"/workspaces/{workspace_id}/documents",
                     files={"file": ("b.pdf", io.BytesIO(content), "application/pdf")},
                     headers=auth_headers)
    assert r1.json()["sha256_hash"] == r2.json()["sha256_hash"]


def test_list_documents(client, auth_headers, workspace_id):
    content = b"test"
    client.post(f"/workspaces/{workspace_id}/documents",
                files={"file": ("doc.pdf", io.BytesIO(content), "application/pdf")},
                headers=auth_headers)
    response = client.get(f"/workspaces/{workspace_id}/documents", headers=auth_headers)
    assert response.status_code == 200
    assert len(response.json()) == 1


def test_empty_file_returns_400(client, auth_headers, workspace_id):
    response = client.post(
        f"/workspaces/{workspace_id}/documents",
        files={"file": ("empty.pdf", io.BytesIO(b""), "application/pdf")},
        headers=auth_headers,
    )
    assert response.status_code == 400
