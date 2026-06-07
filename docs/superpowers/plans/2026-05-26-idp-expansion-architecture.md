# IDP Document Type Expansion Architecture Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make adding a new document type a database-only operation — no code changes — by adding `parse_strategy` and `default_confidence_threshold` to `DocumentSchema`, loading recognized types dynamically from the DB, and wiring the pipeline to read the parse strategy from the schema.

**Architecture:** Three changes work together. (1) A new `parse_strategy` enum column on `document_schemas` tells the pipeline whether to use Claude extraction or direct XML parsing, removing the hardcoded type-check in `xml_parser.py`. (2) `detect_document_type()` loads the known type list from the DB at call time instead of a hardcoded constant — adding a schema row immediately makes the type detectable. (3) `default_confidence_threshold` on each schema gives the extraction evaluator (Phase 2A) a per-schema quality baseline without requiring a separate table.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.0, Alembic, PostgreSQL 16, pytest

---

## File Map

| File | Status | Change |
|------|--------|--------|
| `backend/app/models/document_schema.py` | MODIFY | Add `parse_strategy` and `default_confidence_threshold` fields |
| `backend/alembic/versions/<id>_add_parse_strategy.py` | CREATE | Migration: add columns, set 990/990-T to xml_direct |
| `backend/app/services/xml_parser.py` | MODIFY | Add `is_valid_xml_bytes()` (byte-only check, no type check) |
| `backend/app/services/document_pipeline.py` | MODIFY | Use `schema.parse_strategy` instead of `is_parseable_xml()` |
| `backend/app/services/extraction_engine.py` | MODIFY | `detect_document_type()` loads types from DB; remove `KNOWN_DOCUMENT_TYPES` constant |
| `backend/app/seeds/document_schemas.py` | MODIFY | Add `parse_strategy` and `default_confidence_threshold` to all seed constructors |
| `backend/tests/test_extractions.py` | MODIFY | Add tests for dynamic type loading and parse_strategy routing |
| `backend/tests/test_documents.py` | MODIFY | Add test for file-too-large rejection (already in config, test was missing) |

---

## Task 1: Add parse_strategy and default_confidence_threshold to DocumentSchema

**Files:**
- Modify: `backend/app/models/document_schema.py`
- Create: `backend/alembic/versions/<id>_add_parse_strategy_to_document_schemas.py`

- [ ] **Step 1: Update the model**

Replace the contents of `backend/app/models/document_schema.py`:

```python
import uuid
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, Integer, Boolean, Text, Float
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base

class DocumentSchema(Base):
    __tablename__ = "document_schemas"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    document_type: Mapped[str] = mapped_column(String, nullable=False)
    vertical: Mapped[str] = mapped_column(String, default="general")
    display_name: Mapped[str] = mapped_column(String, nullable=False)
    schema_fields: Mapped[list] = mapped_column(JSONB, default=list)
    extraction_prompt: Mapped[str] = mapped_column(Text, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    parse_strategy: Mapped[str] = mapped_column(
        SAEnum("claude", "xml_direct", name="parse_strategy"),
        default="claude",
        nullable=False,
    )
    default_confidence_threshold: Mapped[float] = mapped_column(
        Float, default=0.7, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
```

- [ ] **Step 2: Generate the Alembic migration**

```bash
cd backend
alembic revision -m "add_parse_strategy_to_document_schemas"
```

This creates a new file in `backend/alembic/versions/`. Open it and replace the `upgrade()` and `downgrade()` functions with:

```python
from alembic import op
from sqlalchemy import text

def upgrade() -> None:
    # Create the parse_strategy enum type
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'parse_strategy') THEN
                CREATE TYPE parse_strategy AS ENUM ('claude', 'xml_direct');
            END IF;
        END $$;
    """)
    # Add parse_strategy column
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'document_schemas' AND column_name = 'parse_strategy'
            ) THEN
                ALTER TABLE document_schemas
                ADD COLUMN parse_strategy parse_strategy NOT NULL DEFAULT 'claude';
            END IF;
        END $$;
    """)
    # Add default_confidence_threshold column
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'document_schemas' AND column_name = 'default_confidence_threshold'
            ) THEN
                ALTER TABLE document_schemas
                ADD COLUMN default_confidence_threshold FLOAT NOT NULL DEFAULT 0.7;
            END IF;
        END $$;
    """)
    # Existing 990 and 990-T schemas use XML direct parse
    op.execute("""
        UPDATE document_schemas
        SET parse_strategy = 'xml_direct',
            default_confidence_threshold = 1.0
        WHERE document_type IN ('990', '990-T');
    """)


def downgrade() -> None:
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'document_schemas' AND column_name = 'default_confidence_threshold'
            ) THEN
                ALTER TABLE document_schemas DROP COLUMN default_confidence_threshold;
            END IF;
        END $$;
    """)
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'document_schemas' AND column_name = 'parse_strategy'
            ) THEN
                ALTER TABLE document_schemas DROP COLUMN parse_strategy;
            END IF;
        END $$;
    """)
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_type WHERE typname = 'parse_strategy') THEN
                DROP TYPE parse_strategy;
            END IF;
        END $$;
    """)
```

- [ ] **Step 3: Apply the migration and verify**

```bash
cd backend
alembic upgrade head
```

Expected output: `Running upgrade a3b8e1f92d44 -> <new_id>, add_parse_strategy_to_document_schemas`

Then verify in the database:

```bash
docker-compose exec db psql -U catalyst -d catalyst -c "\d document_schemas" | grep -E "parse_strategy|confidence"
```

Expected: both columns present.

```bash
docker-compose exec db psql -U catalyst -d catalyst -c "SELECT document_type, parse_strategy, default_confidence_threshold FROM document_schemas WHERE document_type IN ('990', '990-T');"
```

Expected: 990 and 990-T rows show `parse_strategy = xml_direct` and `default_confidence_threshold = 1.0`.

- [ ] **Step 4: Run tests to confirm migration didn't break anything**

```bash
cd backend
pytest tests/ -v --tb=short 2>&1 | tail -5
```

Expected: all tests pass (count unchanged from before this task).

- [ ] **Step 5: Commit**

```bash
git add backend/app/models/document_schema.py backend/alembic/versions/
git commit -m "feat: add parse_strategy and default_confidence_threshold to DocumentSchema"
```

---

## Task 2: Add is_valid_xml_bytes and update pipeline to use parse_strategy

**Files:**
- Modify: `backend/app/services/xml_parser.py`
- Modify: `backend/app/services/document_pipeline.py`
- Modify: `backend/tests/test_extractions.py`

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_extractions.py`:

```python
from unittest.mock import patch, MagicMock
from app.services.xml_parser import is_valid_xml_bytes


def test_is_valid_xml_bytes_returns_true_for_valid_xml():
    xml = b"<?xml version='1.0'?><root><child>value</child></root>"
    assert is_valid_xml_bytes(xml) is True


def test_is_valid_xml_bytes_returns_false_for_non_xml():
    assert is_valid_xml_bytes(b"%PDF-1.4 not xml") is False
    assert is_valid_xml_bytes(b"") is False
    assert is_valid_xml_bytes(b"just some text") is False
```

- [ ] **Step 2: Run to confirm they fail**

```bash
cd backend
pytest tests/test_extractions.py::test_is_valid_xml_bytes_returns_true_for_valid_xml -v
```

Expected: `ImportError` — `is_valid_xml_bytes` not yet defined.

- [ ] **Step 3: Add is_valid_xml_bytes to xml_parser.py**

Append to `backend/app/services/xml_parser.py` (after the existing `is_parseable_xml` function):

```python
def is_valid_xml_bytes(file_bytes: bytes) -> bool:
    """Return True if file_bytes are parseable XML.
    Used by the pipeline to guard the xml_direct parse path. Unlike
    is_parseable_xml(), this does not check document type — the schema's
    parse_strategy field owns that decision.
    """
    if not file_bytes:
        return False
    try:
        ET.fromstring(file_bytes)
        return True
    except ET.ParseError:
        return False
```

- [ ] **Step 4: Run xml_bytes tests**

```bash
cd backend
pytest tests/test_extractions.py -k "xml_bytes" -v
```

Expected: 2 PASS.

- [ ] **Step 5: Write failing test for pipeline routing**

Append to `backend/tests/test_extractions.py`:

```python
import uuid
from app.models.document_schema import DocumentSchema
from app.models.workspace import Workspace


@pytest.fixture
def xml_schema(db):
    ws = Workspace(
        id=str(uuid.uuid4()),
        name="XML Test WS",
        vertical="general",
        created_by=next(
            u.id for u in db.query(__import__('app.models.user', fromlist=['User']).User).limit(1).all()
        ) if db.query(__import__('app.models.user', fromlist=['User']).User).first() else str(uuid.uuid4()),
    )
    # Simpler: create the schema without workspace dependency
    schema = DocumentSchema(
        id=str(uuid.uuid4()),
        document_type="TEST-XML",
        display_name="Test XML Schema",
        vertical="general",
        schema_fields=[{"name": "test_field", "type": "text", "description": "TestElement — test field"}],
        extraction_prompt="Extract fields.",
        version=1,
        is_active=True,
        parse_strategy="xml_direct",
        default_confidence_threshold=1.0,
    )
    db.add(schema)
    db.commit()
    return schema


def test_pipeline_routes_xml_direct_schema_to_xml_parser(db, xml_schema):
    from app.services.document_pipeline import _run_pipeline
    from app.models.workspace import Workspace
    from app.models.user import User
    import uuid

    user = User(
        id=str(uuid.uuid4()),
        email=f"test_{uuid.uuid4()}@test.com",
        full_name="Test",
        password_hash="x",
    )
    db.add(user)
    ws = Workspace(
        id=str(uuid.uuid4()),
        name="WS",
        vertical="general",
        created_by=user.id,
    )
    db.add(ws)
    db.flush()

    valid_xml = b"<?xml version='1.0'?><root><TestElement>hello</TestElement></root>"

    with patch("app.services.document_pipeline.detect_document_type", return_value="TEST-XML"), \
         patch("app.services.document_pipeline.extract_fields") as mock_claude, \
         patch("app.services.document_pipeline.parse_xml_document", return_value=[]) as mock_xml, \
         patch("app.services.document_pipeline.generate_standardized_name", return_value="test.xml"), \
         patch("app.services.document_pipeline.extract_text", return_value="test content"):

        from app.models.document import Document
        doc = Document(
            id=str(uuid.uuid4()),
            workspace_id=ws.id,
            filename="test.xml",
            original_filename="test.xml",
            file_path="/tmp/test.xml",
            file_type="xml",
            sha256_hash="abc123",
            uploaded_by=user.id,
        )
        db.add(doc)
        db.commit()

        _run_pipeline(doc.id, valid_xml, "test.xml", ws.id, user.id, db)

    mock_xml.assert_called_once()
    mock_claude.assert_not_called()
```

- [ ] **Step 6: Run to confirm it fails**

```bash
cd backend
pytest tests/test_extractions.py::test_pipeline_routes_xml_direct_schema_to_xml_parser -v
```

Expected: FAIL — pipeline still uses `is_parseable_xml` which checks doc_type string, not schema.

- [ ] **Step 7: Update document_pipeline.py**

In `backend/app/services/document_pipeline.py`:

Change the import line:
```python
# OLD
from app.services.xml_parser import is_parseable_xml, parse_xml_document
# NEW
from app.services.xml_parser import is_valid_xml_bytes, parse_xml_document
```

Change the extraction routing in `_run_pipeline()` (around line 224):
```python
# OLD
if is_parseable_xml(file_bytes, doc_type):
    raw_extractions = parse_xml_document(file_bytes, schema)
else:
    raw_extractions = extract_fields(ocr_text, schema)

# NEW
if schema.parse_strategy == "xml_direct" and is_valid_xml_bytes(file_bytes):
    raw_extractions = parse_xml_document(file_bytes, schema)
else:
    raw_extractions = extract_fields(ocr_text, schema)
```

- [ ] **Step 8: Run all tests**

```bash
cd backend
pytest tests/ -v --tb=short 2>&1 | tail -10
```

Expected: all tests pass.

- [ ] **Step 9: Commit**

```bash
git add backend/app/services/xml_parser.py backend/app/services/document_pipeline.py backend/tests/test_extractions.py
git commit -m "feat: pipeline reads parse_strategy from schema — xml routing no longer hardcoded"
```

---

## Task 3: Make detect_document_type load known types from the database

**Files:**
- Modify: `backend/app/services/extraction_engine.py`
- Modify: `backend/app/services/document_pipeline.py`
- Modify: `backend/tests/test_extractions.py`

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_extractions.py`:

```python
from app.services.extraction_engine import detect_document_type


def test_detect_document_type_uses_db_schemas(db):
    """detect_document_type should return a type that exists in document_schemas, not 'OTHER'."""
    schema = DocumentSchema(
        id=str(uuid.uuid4()),
        document_type="CUSTOM-DOC",
        display_name="Custom Doc",
        vertical="general",
        schema_fields=[],
        version=1,
        is_active=True,
        parse_strategy="claude",
        default_confidence_threshold=0.7,
    )
    db.add(schema)
    db.commit()

    with patch("app.services.extraction_engine.client") as mock_client:
        mock_resp = MagicMock()
        mock_resp.content = [MagicMock(text='{"document_type": "CUSTOM-DOC"}')]
        mock_client.messages.create.return_value = mock_resp

        result = detect_document_type("some ocr text", db)

    assert result == "CUSTOM-DOC"


def test_detect_document_type_falls_back_to_other_for_unknown_type(db):
    """If Claude returns a type not in the DB, fall back to OTHER."""
    with patch("app.services.extraction_engine.client") as mock_client:
        mock_resp = MagicMock()
        mock_resp.content = [MagicMock(text='{"document_type": "TOTALLY-UNKNOWN"}')]
        mock_client.messages.create.return_value = mock_resp

        result = detect_document_type("some ocr text", db)

    assert result == "OTHER"
```

- [ ] **Step 2: Run to confirm they fail**

```bash
cd backend
pytest tests/test_extractions.py::test_detect_document_type_uses_db_schemas -v
```

Expected: FAIL — `detect_document_type` still takes only `ocr_text` (no `db` parameter).

- [ ] **Step 3: Update extraction_engine.py**

Replace the `KNOWN_DOCUMENT_TYPES` constant and `detect_document_type` function in `backend/app/services/extraction_engine.py`:

```python
# REMOVE this block entirely:
# KNOWN_DOCUMENT_TYPES = [
#     "DEED", "PLAT", "990", ...
# ]

# ADD this import at the top of the file (with the other imports):
from sqlalchemy.orm import Session


def _load_known_types(db: Session) -> list[str]:
    """Load distinct active document types from document_schemas.
    Returns the DB-registered types plus 'OTHER' as a catch-all.
    Called on every detect_document_type() invocation so newly added
    schemas are immediately detectable without redeployment.
    """
    rows = (
        db.query(DocumentSchema.document_type)
        .filter(DocumentSchema.is_active == True)
        .distinct()
        .all()
    )
    return [r[0] for r in rows] + ["OTHER"]


def detect_document_type(ocr_text: str, db: Session) -> str:
    """
    Ask Claude to identify the document type from the first 1500 characters.
    Known types are loaded from document_schemas at call time — adding a
    schema row immediately makes that type detectable. Falls back to 'OTHER'.
    """
    known_types = _load_known_types(db)

    prompt = f"""You are analyzing a document to determine its type.
Based on the text below, identify the document type.

Choose EXACTLY ONE from this list:
{', '.join(known_types)}

Respond with JSON only — no markdown, no explanation:
{{"document_type": "TYPE_HERE"}}

Document text (first 1500 characters):
{ocr_text[:1500]}"""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=50,
            messages=[{"role": "user", "content": prompt}],
        )
        result = json.loads(strip_json_fences(response.content[0].text))
        detected = result.get("document_type", "OTHER")
        return detected if detected in known_types else "OTHER"
    except Exception as e:
        logger.warning(f"Type detection failed: {e}")
        return "OTHER"
```

Also remove the `_get_schema_for_vertical` private helper if it references `KNOWN_DOCUMENT_TYPES` — check the file and clean up any references. The `get_schema_for_type` function does not use the constant, so it stays as-is.

- [ ] **Step 4: Update the caller in document_pipeline.py**

In `backend/app/services/document_pipeline.py`, the call on line ~193:

```python
# OLD
doc_type = detect_document_type(ocr_text)
# NEW
doc_type = detect_document_type(ocr_text, db)
```

- [ ] **Step 5: Run all tests**

```bash
cd backend
pytest tests/ -v --tb=short 2>&1 | tail -10
```

Expected: all tests pass. The `detect_document_type` mock in existing tests patches `app.services.document_pipeline.detect_document_type` directly, so the signature change does not break them.

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/extraction_engine.py backend/app/services/document_pipeline.py backend/tests/test_extractions.py
git commit -m "feat: detect_document_type loads known types from DB — adding a schema row is now sufficient"
```

---

## Task 4: Update all seed functions with parse_strategy and default_confidence_threshold

**Files:**
- Modify: `backend/app/seeds/document_schemas.py`

No new tests needed — the migration test in Task 1 already verifies the column exists and existing schemas have the right values. The seed update ensures FRESH installs match.

- [ ] **Step 1: Update every DocumentSchema(...) constructor in the seed file**

In `backend/app/seeds/document_schemas.py`, locate every `DocumentSchema(...)` instantiation (11 total — one per seed function) and add `parse_strategy` and `default_confidence_threshold`.

For all Claude-extraction schemas (9 schemas: PARCEL-RECORD, DEED, SOS-FILING, UCC, BUILDING-PERMIT, AUDIT-REPORT, SCREENSHOT, OBITUARY, PLAT, CORRESPONDENCE), add:
```python
parse_strategy="claude",
default_confidence_threshold=0.75,
```

For 990:
```python
parse_strategy="xml_direct",
default_confidence_threshold=1.0,
```

For 990-T (if seeded separately):
```python
parse_strategy="xml_direct",
default_confidence_threshold=1.0,
```

Example — the DEED seed function should look like:
```python
schema = DocumentSchema(
    document_type="DEED",
    display_name="Real Property Deed",
    vertical="general",
    schema_fields=schema_fields,
    extraction_prompt=DEED_EXTRACTION_PROMPT,
    version=1,
    is_active=True,
    parse_strategy="claude",
    default_confidence_threshold=0.75,
)
```

- [ ] **Step 2: Add confidence_threshold to required fields in DEED and PARCEL-RECORD seeds**

In the DEED field definitions, update the `required=True` fields to include `confidence_threshold`:

```python
# In DEED_FIELDS (or equivalent), for required fields:
{"name": "instrument_number", "type": "id_number", "description": "...", "required": True, "confidence_threshold": 0.92},
{"name": "grantor",           "type": "name",      "description": "...", "required": True, "confidence_threshold": 0.88},
{"name": "grantee",           "type": "name",      "description": "...", "required": True, "confidence_threshold": 0.88},
{"name": "recording_date",    "type": "date",      "description": "...", "required": True, "confidence_threshold": 0.90},
{"name": "recording_county",  "type": "text",      "description": "...", "required": True, "confidence_threshold": 0.90},
```

In the PARCEL-RECORD IDENTITY section, for required fields:
```python
{"name": "parcel_number",    "type": "id_number", "description": "...", "required": True, "confidence_threshold": 0.95},
{"name": "owner_name",       "type": "name",      "description": "...", "required": True, "confidence_threshold": 0.88},
{"name": "property_address", "type": "address",   "description": "...", "required": True, "confidence_threshold": 0.88},
{"name": "county",           "type": "text",      "description": "...", "required": True, "confidence_threshold": 0.92},
```

Non-required fields do not need `confidence_threshold` — they will fall back to `default_confidence_threshold` on the schema.

- [ ] **Step 3: Verify the seed file is syntactically correct**

```bash
cd backend
python -c "from app.seeds.document_schemas import seed_deed_schema; print('OK')"
```

Expected: `OK` with no errors.

- [ ] **Step 4: Run full test suite**

```bash
cd backend
pytest tests/ -v --tb=short 2>&1 | tail -5
```

Expected: all tests pass.

- [ ] **Step 5: Verify clean migration on fresh database**

```bash
docker-compose exec db psql -U catalyst -c "DROP DATABASE IF EXISTS catalyst_expand_test; CREATE DATABASE catalyst_expand_test;"
docker-compose run --rm -e DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_expand_test backend alembic upgrade head
docker-compose exec db psql -U catalyst -d catalyst_expand_test -c "SELECT version_num FROM alembic_version;"
docker-compose exec db psql -U catalyst -c "DROP DATABASE catalyst_expand_test;"
```

Expected: migration applies cleanly, version_num is the new migration ID.

- [ ] **Step 6: Commit**

```bash
git add backend/app/seeds/document_schemas.py
git commit -m "feat: seed parse_strategy and confidence_threshold — all schemas self-describing"
```

---

## Self-Review

**Spec coverage:**

| Requirement | Task |
|-------------|------|
| `parse_strategy` on DocumentSchema model | Task 1 |
| Migration adds column, updates 990/990-T | Task 1 |
| `is_valid_xml_bytes` byte-only check | Task 2 |
| Pipeline uses `schema.parse_strategy` not type string | Task 2 |
| `detect_document_type` loads types from DB | Task 3 |
| Caller in pipeline passes `db` | Task 3 |
| All seeds include `parse_strategy` | Task 4 |
| `default_confidence_threshold` on schemas | Task 1 + 4 |
| `confidence_threshold` per field on required fields | Task 4 |

**Placeholder scan:** All code blocks are complete. ✓

**Type consistency:** `detect_document_type(ocr_text: str, db: Session)` — called in pipeline as `detect_document_type(ocr_text, db)` — matches. `is_valid_xml_bytes(file_bytes: bytes)` — called in pipeline as `is_valid_xml_bytes(file_bytes)` — matches. ✓
