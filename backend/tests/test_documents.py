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


def test_get_document_file(client, auth_headers, workspace_id):
    content = b"%PDF-1.4 test content"
    upload_response = client.post(
        f"/workspaces/{workspace_id}/documents",
        files={"file": ("test.pdf", io.BytesIO(content), "application/pdf")},
        headers=auth_headers,
    )
    doc_id = upload_response.json()["id"]

    response = client.get(
        f"/workspaces/{workspace_id}/documents/{doc_id}/file",
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert "application/pdf" in response.headers["content-type"]
    assert response.content == content


def test_get_document_file_not_found(client, auth_headers, workspace_id):
    response = client.get(
        f"/workspaces/{workspace_id}/documents/nonexistent-id/file",
        headers=auth_headers,
    )
    assert response.status_code == 404


def test_status_stream_returns_event_stream(client, auth_headers, workspace_id):
    content = b"%PDF-1.4 test"
    doc_id = client.post(
        f"/workspaces/{workspace_id}/documents",
        files={"file": ("test.pdf", io.BytesIO(content), "application/pdf")},
        headers=auth_headers,
    ).json()["id"]

    response = client.get(
        f"/workspaces/{workspace_id}/documents/{doc_id}/status/stream",
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]


def test_export_csv_returns_csv(client, auth_headers, workspace_id, db):
    import io as io_module
    from app.models.document import Document
    from app.models.document_extraction import DocumentExtraction

    doc_id = client.post(
        f"/workspaces/{workspace_id}/documents",
        files={"file": ("export_test.pdf", io_module.BytesIO(b"%PDF-1.4 x"), "application/pdf")},
        headers=auth_headers,
    ).json()["id"]

    doc = db.query(Document).filter(Document.id == doc_id).first()
    doc.extraction_status = "complete"
    db.flush()
    db.add(DocumentExtraction(
        document_id=doc_id,
        workspace_id=workspace_id,
        field_name="sale_amount",
        field_value="285000",
        field_type="currency",
        confidence=0.95,
        attempt=1,
    ))
    db.commit()

    response = client.get(
        f"/workspaces/{workspace_id}/documents/{doc_id}/extractions.csv",
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert "text/csv" in response.headers["content-type"]
    assert "sale_amount" in response.text
    assert "285000" in response.text


def test_export_json_returns_json(client, auth_headers, workspace_id, db):
    import io as io_module
    from app.models.document import Document
    from app.models.document_extraction import DocumentExtraction

    doc_id = client.post(
        f"/workspaces/{workspace_id}/documents",
        files={"file": ("export_test2.pdf", io_module.BytesIO(b"%PDF-1.4 y"), "application/pdf")},
        headers=auth_headers,
    ).json()["id"]

    doc = db.query(Document).filter(Document.id == doc_id).first()
    doc.extraction_status = "complete"
    db.flush()
    db.add(DocumentExtraction(
        document_id=doc_id,
        workspace_id=workspace_id,
        field_name="grantor_name",
        field_value="John Smith",
        field_type="name",
        confidence=0.98,
        attempt=1,
    ))
    db.commit()

    response = client.get(
        f"/workspaces/{workspace_id}/documents/{doc_id}/extractions.json",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert data[0]["field_name"] == "grantor_name"
    assert data[0]["field_value"] == "John Smith"


def test_export_csv_escapes_formula_injection(client, auth_headers, workspace_id, db):
    import io as io_module
    from unittest.mock import patch
    from app.models.document import Document
    from app.models.document_extraction import DocumentExtraction

    with patch("app.routers.documents.process_upload_background"):
        doc_id = client.post(
            f"/workspaces/{workspace_id}/documents",
            files={"file": ("inj.pdf", io_module.BytesIO(b"%PDF-1.4 x"), "application/pdf")},
            headers=auth_headers,
        ).json()["id"]

    doc = db.query(Document).filter(Document.id == doc_id).first()
    doc.extraction_status = "complete"
    db.flush()
    db.add(DocumentExtraction(
        document_id=doc_id, workspace_id=workspace_id,
        field_name="payee", field_value="=2+5+cmd",
        field_type="text", confidence=0.9, attempt=1,
    ))
    db.commit()

    res = client.get(
        f"/workspaces/{workspace_id}/documents/{doc_id}/extractions.csv",
        headers=auth_headers,
    )
    assert res.status_code == 200
    assert "'=2+5+cmd" in res.text          # neutralized with a leading quote
    assert "payee,=2+5+cmd" not in res.text  # never written as a bare formula


def test_export_csv_filename_header_has_no_crlf(client, auth_headers, workspace_id, db):
    import io as io_module
    from unittest.mock import patch
    from app.models.document import Document

    with patch("app.routers.documents.process_upload_background"):
        doc_id = client.post(
            f"/workspaces/{workspace_id}/documents",
            files={"file": ("hdr.pdf", io_module.BytesIO(b"%PDF-1.4 x"), "application/pdf")},
            headers=auth_headers,
        ).json()["id"]

    doc = db.query(Document).filter(Document.id == doc_id).first()
    doc.filename = "evil\r\nSet-Cookie: pwned.pdf"
    doc.extraction_status = "complete"
    db.commit()

    res = client.get(
        f"/workspaces/{workspace_id}/documents/{doc_id}/extractions.csv",
        headers=auth_headers,
    )
    assert res.status_code == 200
    cd = res.headers["content-disposition"]
    assert "\r" not in cd
    assert "\n" not in cd
    assert cd.startswith("attachment;")
    assert "filename*=UTF-8''" in cd   # only the fixed code emits RFC 5987 form
    assert "set-cookie" not in res.headers


def test_upload_rejects_disallowed_extension(client, auth_headers, workspace_id):
    res = client.post(
        f"/workspaces/{workspace_id}/documents",
        files={"file": ("evil.exe", io.BytesIO(b"MZ\x90\x00"), "application/octet-stream")},
        headers=auth_headers,
    )
    assert res.status_code == 415


def test_upload_allows_allowed_extension(client, auth_headers, workspace_id):
    from unittest.mock import patch
    with patch("app.routers.documents.process_upload_background"):
        res = client.post(
            f"/workspaces/{workspace_id}/documents",
            files={"file": ("ok.pdf", io.BytesIO(b"%PDF-1.4 x"), "application/pdf")},
            headers=auth_headers,
        )
    assert res.status_code == 201


def test_served_pdf_is_inline_with_nosniff(client, auth_headers, workspace_id):
    from unittest.mock import patch
    with patch("app.routers.documents.process_upload_background"):
        doc_id = client.post(
            f"/workspaces/{workspace_id}/documents",
            files={"file": ("doc.pdf", io.BytesIO(b"%PDF-1.4 x"), "application/pdf")},
            headers=auth_headers,
        ).json()["id"]
    res = client.get(
        f"/workspaces/{workspace_id}/documents/{doc_id}/file",
        headers=auth_headers,
    )
    assert res.status_code == 200
    assert res.headers["x-content-type-options"] == "nosniff"
    assert res.headers["content-disposition"].startswith("inline")


def test_served_csv_is_attachment(client, auth_headers, workspace_id):
    from unittest.mock import patch
    with patch("app.routers.documents.process_upload_background"):
        doc_id = client.post(
            f"/workspaces/{workspace_id}/documents",
            files={"file": ("data.csv", io.BytesIO(b"a,b\n1,2\n"), "text/csv")},
            headers=auth_headers,
        ).json()["id"]
    res = client.get(
        f"/workspaces/{workspace_id}/documents/{doc_id}/file",
        headers=auth_headers,
    )
    assert res.status_code == 200
    assert res.headers["x-content-type-options"] == "nosniff"
    assert res.headers["content-disposition"].startswith("attachment")
