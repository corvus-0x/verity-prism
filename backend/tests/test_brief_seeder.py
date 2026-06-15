from app.models.document import Document
from app.models.document_extraction import DocumentExtraction
from app.services.synthesis_service import _assemble_evidence
from tests.evals.brief_seeder import seed_fixture


def test_seed_fixture_creates_queryable_workspace(db):
    fixture = {
        "id": "t",
        "vertical": "general",
        "documents": [
            {"key": "d1", "doc_type": "DEED", "sha256": "AAA", "uploaded_at": "2021-03-01"}
        ],
        "extractions": [
            {
                "doc": "d1",
                "field": "sale_amount",
                "value": "50000",
                "type": "currency",
                "confidence": 0.9,
            }
        ],
    }
    ws_id = seed_fixture(fixture, db)

    docs = db.query(Document).filter(Document.workspace_id == ws_id).all()
    exts = db.query(DocumentExtraction).filter(DocumentExtraction.workspace_id == ws_id).all()
    assert len(docs) == 1 and len(exts) == 1

    evidence, documents, required = _assemble_evidence(ws_id, db)
    assert len(evidence) == 1
    assert evidence[0].field_value == "50000"
    assert documents[0].sha256_hash == "AAA"


def test_seed_fixture_with_schema_sets_required_fields(db):
    fixture = {
        "id": "s",
        "vertical": "general",
        "schema": {
            "document_type": "DEED",
            "fields": [
                {"name": "recording_date", "required": True},
                {"name": "grantor_name", "required": True},
            ],
        },
        "documents": [
            {"key": "d1", "doc_type": "DEED", "sha256": "H1", "uploaded_at": "2020-01-10"}
        ],
        "extractions": [
            {"doc": "d1", "field": "recording_date", "value": "2020-01-10", "type": "date"}
        ],
    }
    ws_id = seed_fixture(fixture, db)
    _, _, required = _assemble_evidence(ws_id, db)
    assert any("grantor_name" in v for v in required.values())
