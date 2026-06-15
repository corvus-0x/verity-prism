"""
Seed a golden eval fixture into the test DB as a real workspace.

Inserts a User (FK), Workspace (with vertical), optional DocumentSchema (for
missing_field fixtures), Documents, and DocumentExtraction rows — so
synthesize_brief runs against it exactly as in production. FKs are enforced;
db.flush() makes each parent visible before its FK-dependent child.
"""

import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.document_extraction import DocumentExtraction
from app.models.document_schema import DocumentSchema
from app.models.user import User
from app.models.workspace import Workspace


def seed_fixture(fixture: dict, db: Session) -> str:
    """Insert the fixture's workspace/documents/extractions; return workspace_id."""
    vertical = fixture.get("vertical", "general")

    user = User(
        id=str(uuid.uuid4()),
        email=f"{uuid.uuid4()}@example.com",
        password_hash="x",
        full_name="Eval Seeder",
    )
    db.add(user)
    db.flush()

    ws = Workspace(
        id=str(uuid.uuid4()),
        name=f"eval-{fixture['id']}",
        vertical=vertical,
        created_by=user.id,
    )
    db.add(ws)
    db.flush()

    schema_id = None
    schema_def = fixture.get("schema")
    if schema_def:
        schema = DocumentSchema(
            id=str(uuid.uuid4()),
            document_type=schema_def.get("document_type", "EVAL_DOC"),
            display_name="Eval Schema",
            vertical=vertical,
            schema_fields=schema_def["fields"],
            extraction_prompt="eval",
            version=1,
            is_active=True,
            parse_strategy="claude",
            default_confidence_threshold=0.85,
        )
        db.add(schema)
        db.flush()
        schema_id = schema.id

    doc_id_by_key: dict[str, str] = {}
    for d in fixture["documents"]:
        doc = Document(
            id=str(uuid.uuid4()),
            workspace_id=ws.id,
            filename=f"{d['key']}.pdf",
            original_filename=f"{d['key']}.pdf",
            file_path=f"/eval/{d['key']}.pdf",
            file_type="pdf",
            sha256_hash=d["sha256"],
            uploaded_by=user.id,
            detected_doc_type=d.get("doc_type"),
            schema_id=schema_id,
        )
        if d.get("uploaded_at"):
            doc.uploaded_at = datetime.fromisoformat(d["uploaded_at"])
        db.add(doc)
        db.flush()
        doc_id_by_key[d["key"]] = doc.id

    for e in fixture["extractions"]:
        db.add(
            DocumentExtraction(
                id=str(uuid.uuid4()),
                document_id=doc_id_by_key[e["doc"]],
                workspace_id=ws.id,
                field_name=e["field"],
                field_value=e["value"],
                field_type=e.get("type", "text"),
                confidence=e.get("confidence", 0.95),
            )
        )
    db.commit()
    return ws.id
