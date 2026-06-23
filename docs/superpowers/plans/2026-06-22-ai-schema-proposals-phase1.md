# AI Schema Proposals — Phase 1 (Proposal Backbone) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the data + versioning + validation + reprocess substrate that both schema-proposal features sit on, with the active-schema uniqueness invariant enforced at the database layer.

**Architecture:** A new `schema_change_proposals` table holds AI-drafted schema changes through a `draft → rejected | applied | failed` lifecycle. A Postgres partial unique index makes two active schemas for the same `(document_type, vertical)` impossible. A `validate_proposal()` service gates every apply, a `supersede_schema()` helper performs atomic v1→v2 swaps, and a `reprocess_document()` service re-extracts a document against a forced schema without re-running type detection. No AI proposer code ships in Phase 1 — this is the correctness machinery that the noisy AI half (Phase 2) will run against.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.0 (`Mapped`/`mapped_column`), Alembic, PostgreSQL 16, pytest. Tests run in Docker against `catalyst_test`.

## Global Constraints

- **PRD source of truth:** `.claude/PRPs/prds/ai-schema-proposals.prd.md`. This plan implements **Phase 1 only**.
- **Tests require Docker** (DB access). Every `pytest …` step below runs through this wrapper:
  `docker-compose run --rm -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test backend pytest <args> --ignore=tests/evals`
- **Branch:** all work on `feat/ai-schema-proposals` (create before Task 1). Never commit to `main`.
- **Soft deletes everywhere:** every soft-deletable model gets `is_deleted` / `deleted_at`; every query filters `is_deleted == False`. The `check_soft_delete.py` PostToolUse hook flags omissions.
- **Thin routers:** no Phase 1 router work, but all DB logic lives in `app/services/*.py`. The `check_thin_routers.py` hook enforces this in later phases.
- **Service docstrings:** every function in `app/services/` gets one concise docstring block (what it does; why, only if non-obvious).
- **Import gotcha:** when adding an import, include its first usage in the *same* edit — the ruff `--fix` hook strips imports unused at write time.
- **Valid field types** (the `extraction_field_type` set, copied verbatim): `name`, `date`, `currency`, `address`, `id_number`, `text`, `boolean`.
- **TDD:** write the failing test first, run it red, implement minimally, run it green, commit.

---

## File Structure

| File | Responsibility | Created/Modified |
|------|----------------|------------------|
| `backend/app/models/schema_proposal.py` | `SchemaChangeProposal` ORM model | Create |
| `backend/app/models/__init__.py` | Register the new model for metadata/migrations | Modify |
| `backend/app/models/document_schema.py` | Add partial-unique `__table_args__` for active schemas | Modify |
| `backend/alembic/versions/<gen>_schema_proposals.py` | Table + partial unique index migration | Create (via `/gen-migration`) |
| `backend/app/services/schema_proposal_service.py` | `validate_proposal()`, `supersede_schema()` | Create |
| `backend/app/services/extraction_engine.py` | Harden `get_schema_for_type` ordering | Modify |
| `backend/app/services/document_service.py` | `reprocess_document()` forced-schema path | Modify |
| `backend/tests/test_schema_proposals.py` | All Phase 1 tests | Create |

---

### Task 1: `SchemaChangeProposal` model + active-schema uniqueness index + migration

**Files:**
- Create: `backend/app/models/schema_proposal.py`
- Modify: `backend/app/models/__init__.py`
- Modify: `backend/app/models/document_schema.py`
- Create: `backend/alembic/versions/<generated>_schema_proposals.py`
- Test: `backend/tests/test_schema_proposals.py`

**Interfaces:**
- Produces: `SchemaChangeProposal` ORM model with columns:
  `id: str`, `workspace_id: str`, `document_id: str | None`, `base_schema_id: str | None`,
  `proposal_type: str` (`'new_schema' | 'schema_extension'`),
  `status: str` (`'draft' | 'rejected' | 'applied' | 'failed'`, default `'draft'`),
  `proposed_schema: dict` (JSONB — schema metadata: `document_type`, `display_name`, `vertical`, `parse_strategy`, `default_confidence_threshold`, `extraction_prompt`),
  `proposed_fields: list` (JSONB — field dicts),
  `rationale: str | None`, `created_by_ai: bool`,
  `model_id: str | None`, `prompt_version: str | None`, `proposer_inputs: dict` (JSONB provenance),
  `reviewed_by: str | None`, `reviewed_at: datetime | None`, `apply_error: str | None`,
  `created_at: datetime`, `is_deleted: bool`, `deleted_at: datetime | None`.
- Produces: partial unique index `uq_active_schema_type_vertical` on `document_schemas (document_type, vertical) WHERE is_active = true`.

- [ ] **Step 1: Create the model file**

Create `backend/app/models/schema_proposal.py`:

```python
import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class SchemaChangeProposal(Base):
    __tablename__ = "schema_change_proposals"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id: Mapped[str] = mapped_column(String, ForeignKey("workspaces.id"), nullable=False)
    document_id: Mapped[str] = mapped_column(String, ForeignKey("documents.id"), nullable=True)
    base_schema_id: Mapped[str] = mapped_column(
        String, ForeignKey("document_schemas.id"), nullable=True
    )
    proposal_type: Mapped[str] = mapped_column(
        SAEnum("new_schema", "schema_extension", name="proposal_type"), nullable=False
    )
    status: Mapped[str] = mapped_column(
        SAEnum("draft", "rejected", "applied", "failed", name="proposal_status"),
        default="draft",
        nullable=False,
    )
    proposed_schema: Mapped[dict] = mapped_column(JSONB, default=dict)
    proposed_fields: Mapped[list] = mapped_column(JSONB, default=list)
    rationale: Mapped[str] = mapped_column(Text, nullable=True)
    created_by_ai: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # Provenance — schema changes are engine-contract changes; record why this was proposed.
    model_id: Mapped[str] = mapped_column(String, nullable=True)
    prompt_version: Mapped[str] = mapped_column(String, nullable=True)
    proposer_inputs: Mapped[dict] = mapped_column(JSONB, default=dict)
    # Review tracking — independent of outcome status.
    reviewed_by: Mapped[str] = mapped_column(String, ForeignKey("users.id"), nullable=True)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    apply_error: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    deleted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
```

- [ ] **Step 2: Register the model**

In `backend/app/models/__init__.py`, add the import (alphabetically near the others) and the `__all__` entry in the same edit:

```python
from app.models.schema_proposal import SchemaChangeProposal
```

Add `"SchemaChangeProposal",` to the `__all__` list.

- [ ] **Step 3: Add the partial unique index to `DocumentSchema`**

In `backend/app/models/document_schema.py`, add `text` and `Index` to the existing imports and the `__table_args__` in the same edit. After the imports, the class gains:

```python
from sqlalchemy import Boolean, DateTime, Float, Index, Integer, String, Text, text
# ... (keep existing Enum + JSONB + orm imports) ...


class DocumentSchema(Base):
    __tablename__ = "document_schemas"
    __table_args__ = (
        Index(
            "uq_active_schema_type_vertical",
            "document_type",
            "vertical",
            unique=True,
            postgresql_where=text("is_active = true"),
        ),
    )
```

- [ ] **Step 4: Write the failing test**

Create `backend/tests/test_schema_proposals.py`:

```python
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
        hashed_password="x",
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
```

- [ ] **Step 5: Generate the migration**

Run the project migration skill (autogenerates inside Docker, wires `down_revision`):

```
/gen-migration "add schema_change_proposals table and active-schema partial unique index"
```

Then open the generated file under `backend/alembic/versions/` and **verify two things are present**; add whichever is missing:

1. `op.create_table("schema_change_proposals", ...)` with the enum types `proposal_type` and `proposal_status`.
2. The partial unique index. If autogenerate omitted it (it sometimes drops `postgresql_where`), add to `upgrade()`:

```python
op.create_index(
    "uq_active_schema_type_vertical",
    "document_schemas",
    ["document_type", "vertical"],
    unique=True,
    postgresql_where=sa.text("is_active = true"),
)
```

and to `downgrade()`:

```python
op.drop_index("uq_active_schema_type_vertical", table_name="document_schemas")
```

> **Pre-existing-data guard:** if the dev/test DB already has duplicate active `(document_type, vertical)` rows, `create_index` will fail. The seed data is one active row per type, so this should be clean — but if it fails, that failure is a real finding (it means the ambiguity already exists), not a migration bug. Resolve by deactivating duplicates before the index is created.

- [ ] **Step 6: Run the test to verify it passes (schema applied via migration)**

Run:
```
docker-compose run --rm -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test backend pytest tests/test_schema_proposals.py::test_proposal_persists_with_defaults -v --ignore=tests/evals
```
Expected: PASS (the `migrate_db` session fixture runs `alembic upgrade head`, creating the table).

- [ ] **Step 7: Write the failing test for the DB uniqueness invariant**

Append to `backend/tests/test_schema_proposals.py`:

```python
def test_db_rejects_second_active_schema_for_same_type_vertical(db):
    s1 = DocumentSchema(
        id=str(uuid.uuid4()), document_type="PERMIT", display_name="Permit",
        vertical="general", schema_fields=[], version=1, is_active=True,
        parse_strategy="claude", default_confidence_threshold=0.7,
    )
    db.add(s1)
    db.commit()
    s2 = DocumentSchema(
        id=str(uuid.uuid4()), document_type="PERMIT", display_name="Permit v2",
        vertical="general", schema_fields=[], version=2, is_active=True,
        parse_strategy="claude", default_confidence_threshold=0.7,
    )
    db.add(s2)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_db_allows_second_schema_when_first_is_inactive(db):
    s1 = DocumentSchema(
        id=str(uuid.uuid4()), document_type="PERMIT", display_name="Permit",
        vertical="general", schema_fields=[], version=1, is_active=False,
        parse_strategy="claude", default_confidence_threshold=0.7,
    )
    db.add(s1)
    db.commit()
    s2 = DocumentSchema(
        id=str(uuid.uuid4()), document_type="PERMIT", display_name="Permit v2",
        vertical="general", schema_fields=[], version=2, is_active=True,
        parse_strategy="claude", default_confidence_threshold=0.7,
    )
    db.add(s2)
    db.commit()  # must NOT raise
    db.refresh(s2)
    assert s2.is_active is True
```

- [ ] **Step 8: Run the uniqueness tests**

Run:
```
docker-compose run --rm -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test backend pytest tests/test_schema_proposals.py -v --ignore=tests/evals
```
Expected: all three PASS. If `test_db_rejects_second_active_schema…` fails (commit succeeds), the partial index is missing from the migration — return to Step 5.

- [ ] **Step 9: Commit**

```bash
git add backend/app/models/schema_proposal.py backend/app/models/__init__.py \
        backend/app/models/document_schema.py backend/alembic/versions/ \
        backend/tests/test_schema_proposals.py
git commit -m "feat: schema_change_proposals table + DB-enforced active-schema uniqueness"
```

---

### Task 2: Harden `get_schema_for_type` ordering (defense in depth)

**Files:**
- Modify: `backend/app/services/extraction_engine.py:108-136` (`_get_schema_for_vertical`)
- Test: `backend/tests/test_schema_proposals.py`

**Interfaces:**
- Consumes: `DocumentSchema` rows.
- Produces: `get_schema_for_type(doc_type, db, workspace_vertical)` now returns the **highest-version active** schema when multiple exist (the DB index makes >1 active impossible, but ordering removes any reliance on insertion order).

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_schema_proposals.py`:

```python
from app.services.extraction_engine import get_schema_for_type


def test_get_schema_for_type_prefers_active_highest_version(db):
    old = DocumentSchema(
        id=str(uuid.uuid4()), document_type="PERMIT", display_name="Permit",
        vertical="general", schema_fields=[], version=1, is_active=False,
        parse_strategy="claude", default_confidence_threshold=0.7,
    )
    new = DocumentSchema(
        id=str(uuid.uuid4()), document_type="PERMIT", display_name="Permit v2",
        vertical="general", schema_fields=[], version=2, is_active=True,
        parse_strategy="claude", default_confidence_threshold=0.7,
    )
    db.add_all([old, new])
    db.commit()
    result = get_schema_for_type("PERMIT", db, "general")
    assert result is not None
    assert result.id == new.id
    assert result.version == 2
```

- [ ] **Step 2: Run the test to verify it fails (or passes by luck)**

Run:
```
docker-compose run --rm -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test backend pytest tests/test_schema_proposals.py::test_get_schema_for_type_prefers_active_highest_version -v --ignore=tests/evals
```
Expected: PASS already (only `new` is active) — but the assertion currently relies on `.first()` returning the only active row. Step 3 makes it deterministic regardless of future paths.

- [ ] **Step 3: Add explicit ordering**

In `backend/app/services/extraction_engine.py`, in `_get_schema_for_vertical`, add `.order_by(DocumentSchema.version.desc())` before each `.first()`. The vertical-specific branch becomes:

```python
    if workspace_vertical != "general":
        schema = (
            db.query(DocumentSchema)
            .filter(
                DocumentSchema.document_type == doc_type,
                DocumentSchema.vertical == workspace_vertical,
                DocumentSchema.is_active == True,  # noqa: E712
            )
            .order_by(DocumentSchema.version.desc())
            .first()
        )
        if schema:
            return schema
    return (
        db.query(DocumentSchema)
        .filter(
            DocumentSchema.document_type == doc_type,
            DocumentSchema.vertical == "general",
            DocumentSchema.is_active == True,  # noqa: E712
        )
        .order_by(DocumentSchema.version.desc())
        .first()
    )
```

- [ ] **Step 4: Run the test + the existing extraction-engine tests**

Run:
```
docker-compose run --rm -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test backend pytest tests/test_schema_proposals.py::test_get_schema_for_type_prefers_active_highest_version tests/test_extraction_engine.py -v --ignore=tests/evals
```
Expected: all PASS (no regression in existing extraction-engine behavior).

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/extraction_engine.py backend/tests/test_schema_proposals.py
git commit -m "feat: deterministic active-schema selection by version desc"
```

---

### Task 3: `validate_proposal()` — server-side apply gate

**Files:**
- Create: `backend/app/services/schema_proposal_service.py`
- Test: `backend/tests/test_schema_proposals.py`

**Interfaces:**
- Consumes: `SchemaChangeProposal`, `DocumentSchema`, a `Session`.
- Produces: `validate_proposal(proposal: SchemaChangeProposal, db: Session) -> list[str]` — returns a list of human-readable error strings; **empty list means valid**. Rules: field names unique (within proposal and vs. base schema for extensions); `snake_case`; `field_type` in the valid set; no reserved names; thresholds in `[0.0, 1.0]`; non-empty `description`; ≥1 field; for `new_schema`: `document_type` matches upper-kebab, `display_name` present, and no existing active `(document_type, vertical)`.
- Produces: module constants `VALID_FIELD_TYPES`, `RESERVED_FIELD_NAMES`.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_schema_proposals.py`:

```python
from app.services.schema_proposal_service import validate_proposal


def _new_schema_proposal(**meta_over):
    meta = {"document_type": "PERMIT", "display_name": "Permit", "vertical": "general"}
    meta.update(meta_over)
    return SchemaChangeProposal(
        workspace_id="ws", proposal_type="new_schema", proposed_schema=meta,
        proposed_fields=[{"name": "permit_no", "type": "id_number", "description": "Permit number"}],
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
    db.add(DocumentSchema(
        id=str(uuid.uuid4()), document_type="PERMIT", display_name="Permit",
        vertical="general", schema_fields=[], version=1, is_active=True,
        parse_strategy="claude", default_confidence_threshold=0.7,
    ))
    db.commit()
    errors = validate_proposal(_new_schema_proposal(), db)
    assert any("already" in e for e in errors)


def test_validate_extension_rejects_field_clashing_with_base(db):
    base = DocumentSchema(
        id=str(uuid.uuid4()), document_type="DEED", display_name="Deed",
        vertical="general",
        schema_fields=[{"name": "grantor_name", "type": "name", "description": "g"}],
        version=1, is_active=True, parse_strategy="claude", default_confidence_threshold=0.7,
    )
    db.add(base)
    db.commit()
    p = SchemaChangeProposal(
        workspace_id="ws", proposal_type="schema_extension", base_schema_id=base.id,
        proposed_schema={}, proposed_fields=[
            {"name": "grantor_name", "type": "name", "description": "dup of base"},
        ],
    )
    errors = validate_proposal(p, db)
    assert any("duplicate" in e for e in errors)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:
```
docker-compose run --rm -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test backend pytest tests/test_schema_proposals.py -k validate -v --ignore=tests/evals
```
Expected: FAIL with `ModuleNotFoundError: app.services.schema_proposal_service`.

- [ ] **Step 3: Implement `validate_proposal`**

Create `backend/app/services/schema_proposal_service.py`:

```python
"""Schema proposal backbone: server-side validation and atomic supersession.

validate_proposal() is the apply gate — it runs regardless of who edited the
draft, because a human reviewer is necessary but not sufficient for an
engine-contract change. supersede_schema() performs the v1->v2 swap in one
transaction so the active-schema invariant is never momentarily violated.
"""

import re

from sqlalchemy.orm import Session

from app.models.document_schema import DocumentSchema
from app.models.schema_proposal import SchemaChangeProposal

VALID_FIELD_TYPES = {"name", "date", "currency", "address", "id_number", "text", "boolean"}
RESERVED_FIELD_NAMES = {
    "id", "document_id", "workspace_id", "schema_id", "field_name", "field_value",
    "field_type", "confidence", "ocr_confidence", "attempt",
}
_SNAKE_CASE = re.compile(r"^[a-z][a-z0-9_]*$")
_DOC_TYPE = re.compile(r"^[A-Z0-9]+(-[A-Z0-9]+)*$")
_THRESHOLD_KEYS = ("confidence_threshold", "ai_threshold", "ocr_threshold")


def validate_proposal(proposal: SchemaChangeProposal, db: Session) -> list[str]:
    """Return a list of validation errors for a proposal; empty list means valid.

    Enforced on apply (not just at draft time): field-name shape/uniqueness,
    known field types, threshold ranges, descriptions, and — for new schemas —
    a normalized document_type with no active collision.
    """
    errors: list[str] = []
    meta = proposal.proposed_schema or {}
    fields = proposal.proposed_fields or []

    if proposal.proposal_type == "new_schema":
        doc_type = meta.get("document_type") or ""
        vertical = meta.get("vertical") or "general"
        if not _DOC_TYPE.match(doc_type):
            errors.append(
                f"document_type '{doc_type}' must be UPPER-KEBAB (e.g. PARCEL-RECORD)"
            )
        if not (meta.get("display_name") or "").strip():
            errors.append("display_name is required")
        if doc_type:
            existing = (
                db.query(DocumentSchema)
                .filter(
                    DocumentSchema.document_type == doc_type,
                    DocumentSchema.vertical == vertical,
                    DocumentSchema.is_active == True,  # noqa: E712
                )
                .first()
            )
            if existing:
                errors.append(
                    f"an active schema already exists for ({doc_type}, {vertical}) — "
                    "use a schema_extension instead"
                )

    base_names: set[str] = set()
    if proposal.proposal_type == "schema_extension" and proposal.base_schema_id:
        base = (
            db.query(DocumentSchema)
            .filter(DocumentSchema.id == proposal.base_schema_id)
            .first()
        )
        if base:
            base_names = {f.get("name") for f in (base.schema_fields or [])}

    if not fields:
        errors.append("proposal must contain at least one field")

    seen: set[str] = set()
    for f in fields:
        name = f.get("name") or ""
        if not _SNAKE_CASE.match(name):
            errors.append(f"field '{name}' must be snake_case")
        if name in RESERVED_FIELD_NAMES:
            errors.append(f"field '{name}' is a reserved name")
        if name in seen or name in base_names:
            errors.append(f"duplicate field name '{name}'")
        seen.add(name)
        if f.get("type") not in VALID_FIELD_TYPES:
            errors.append(
                f"field '{name}' has invalid field_type '{f.get('type')}' "
                f"(allowed: {', '.join(sorted(VALID_FIELD_TYPES))})"
            )
        if not (f.get("description") or "").strip():
            errors.append(f"field '{name}' is missing a description")
        for key in _THRESHOLD_KEYS:
            if key in f:
                val = f[key]
                if not isinstance(val, (int, float)) or not (0.0 <= val <= 1.0):
                    errors.append(f"field '{name}' {key} must be between 0.0 and 1.0")

    return errors
```

- [ ] **Step 4: Run the tests to verify they pass**

Run:
```
docker-compose run --rm -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test backend pytest tests/test_schema_proposals.py -k validate -v --ignore=tests/evals
```
Expected: all `validate` tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/schema_proposal_service.py backend/tests/test_schema_proposals.py
git commit -m "feat: validate_proposal server-side apply gate"
```

---

### Task 4: `supersede_schema()` — atomic v1→v2 swap

**Files:**
- Modify: `backend/app/services/schema_proposal_service.py`
- Test: `backend/tests/test_schema_proposals.py`

**Interfaces:**
- Consumes: a base `DocumentSchema`, a merged field list, a `Session`.
- Produces: `supersede_schema(db: Session, base: DocumentSchema, new_fields: list[dict]) -> DocumentSchema` — in one transaction sets `base.is_active = False` and inserts a new `DocumentSchema` copying base metadata with `version = base.version + 1`, `is_active = True`, and `schema_fields = new_fields`. Returns the new active schema. Used by Phase 2's `apply_schema_proposal` for the extension path.

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_schema_proposals.py`:

```python
from app.services.schema_proposal_service import supersede_schema


def test_supersede_schema_swaps_active_version_atomically(db):
    base = DocumentSchema(
        id=str(uuid.uuid4()), document_type="DEED", display_name="Deed",
        vertical="general",
        schema_fields=[{"name": "grantor_name", "type": "name", "description": "g"}],
        version=1, is_active=True, parse_strategy="claude", default_confidence_threshold=0.75,
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
```

- [ ] **Step 2: Run the test to verify it fails**

Run:
```
docker-compose run --rm -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test backend pytest tests/test_schema_proposals.py::test_supersede_schema_swaps_active_version_atomically -v --ignore=tests/evals
```
Expected: FAIL with `ImportError: cannot import name 'supersede_schema'`.

- [ ] **Step 3: Implement `supersede_schema`**

Add to `backend/app/services/schema_proposal_service.py` (the `DocumentSchema` import is already present):

```python
def supersede_schema(
    db: Session, base: DocumentSchema, new_fields: list[dict]
) -> DocumentSchema:
    """Deactivate `base` and insert its successor (version+1) in one transaction.

    Why one transaction: the partial unique index forbids two active schemas for
    the same (document_type, vertical). Deactivating the base and inserting the
    successor must commit together, or the insert would either collide (if base
    stays active) or leave a window with no active schema.
    """
    base.is_active = False
    db.flush()  # release the active slot before inserting the successor
    successor = DocumentSchema(
        document_type=base.document_type,
        vertical=base.vertical,
        display_name=base.display_name,
        schema_fields=new_fields,
        extraction_prompt=base.extraction_prompt,
        version=base.version + 1,
        is_active=True,
        parse_strategy=base.parse_strategy,
        default_confidence_threshold=base.default_confidence_threshold,
    )
    db.add(successor)
    db.commit()
    db.refresh(successor)
    return successor
```

- [ ] **Step 4: Run the test to verify it passes**

Run:
```
docker-compose run --rm -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test backend pytest tests/test_schema_proposals.py::test_supersede_schema_swaps_active_version_atomically -v --ignore=tests/evals
```
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/schema_proposal_service.py backend/tests/test_schema_proposals.py
git commit -m "feat: atomic schema supersession helper"
```

---

### Task 5: `reprocess_document()` — forced-schema re-extraction

**Files:**
- Modify: `backend/app/services/document_service.py`
- Test: `backend/tests/test_schema_proposals.py`

**Interfaces:**
- Consumes: `Document`, `DocumentSchema`, `extract_fields`, `save_extractions` (from `extraction_engine`), a `Session`.
- Produces: `reprocess_document(document_id: str, schema_id: str, db: Session) -> Document` — pins the document to `schema_id` (sets `schema_id` and `detected_doc_type` to the schema's `document_type`, **skipping type detection**), clears prior extractions, re-extracts from the document's stored `ocr_text`, saves new rows, sets `extraction_status` to `complete` (or `needs_review` if a claude schema with fields yields zero), and writes an audit row. Raises `ValueError` if the document has no `ocr_text` or the schema is missing.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_schema_proposals.py`:

```python
from unittest.mock import patch

from app.models.document import Document
from app.models.document_extraction import DocumentExtraction
from app.services import document_service


def _doc_with_ocr(db, ws, user, schema_id=None, status="no_schema", ocr="Permit No 12345"):
    doc = Document(
        id=str(uuid.uuid4()), workspace_id=ws.id, filename="permit.pdf",
        original_filename="permit.pdf", file_path="/tmp/permit.pdf", file_type="pdf",
        sha256_hash=str(uuid.uuid4()), uploaded_by=user.id,
        extraction_status=status, schema_id=schema_id, ocr_text=ocr,
    )
    db.add(doc)
    db.commit()
    return doc


def test_reprocess_document_forces_schema_without_detection(db):
    user = _user(db)
    ws = _workspace(db, user)
    schema = DocumentSchema(
        id=str(uuid.uuid4()), document_type="PERMIT", display_name="Permit",
        vertical="general",
        schema_fields=[{"name": "permit_no", "type": "id_number", "description": "Permit number"}],
        version=1, is_active=True, parse_strategy="claude", default_confidence_threshold=0.7,
    )
    db.add(schema)
    db.commit()
    doc = _doc_with_ocr(db, ws, user)

    fake_rows = [
        {"field_name": "permit_no", "field_value": "12345", "field_type": "id_number",
         "confidence": 0.95, "ocr_confidence": 0.95}
    ]
    # detect_document_type must NOT be called; extract_fields is forced on the given schema.
    # Patch at the SOURCE module (extraction_engine) — reprocess_document never imports
    # detect_document_type, so there is no name to patch on document_service, and the ruff
    # --fix hook would strip any unused import anyway.
    with patch("app.services.extraction_engine.detect_document_type") as detect, \
         patch("app.services.document_service.extract_fields", return_value=fake_rows):
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
        id=str(uuid.uuid4()), document_type="PERMIT", display_name="Permit",
        vertical="general",
        schema_fields=[{"name": "permit_no", "type": "id_number", "description": "Permit number"}],
        version=1, is_active=True, parse_strategy="claude", default_confidence_threshold=0.7,
    )
    db.add(schema)
    db.commit()
    doc = _doc_with_ocr(db, ws, user, schema_id=schema.id, status="complete")
    db.add(DocumentExtraction(
        id=str(uuid.uuid4()), document_id=doc.id, workspace_id=ws.id,
        field_name="stale_field", field_value="old", field_type="text",
        confidence=0.5, schema_id=schema.id, attempt=1,
    ))
    db.commit()

    fake_rows = [
        {"field_name": "permit_no", "field_value": "999", "field_type": "id_number",
         "confidence": 0.9, "ocr_confidence": 0.9}
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
        id=str(uuid.uuid4()), document_type="PERMIT", display_name="Permit",
        vertical="general", schema_fields=[], version=1, is_active=True,
        parse_strategy="claude", default_confidence_threshold=0.7,
    )
    db.add(schema)
    db.commit()
    doc = _doc_with_ocr(db, ws, user, ocr=None)
    with pytest.raises(ValueError, match="ocr_text"):
        document_service.reprocess_document(doc.id, schema.id, db)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:
```
docker-compose run --rm -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test backend pytest tests/test_schema_proposals.py -k reprocess -v --ignore=tests/evals
```
Expected: FAIL with `AttributeError: module 'app.services.document_service' has no attribute 'reprocess_document'`.

- [ ] **Step 3: Implement `reprocess_document`**

In `backend/app/services/document_service.py`, add the imports (with usage in the same edit) and the function. Add to the existing import block:

```python
from app.models.document import Document
from app.models.document_extraction import DocumentExtraction
from app.models.document_schema import DocumentSchema
from app.services import audit
from app.services.extraction_engine import extract_fields, save_extractions
```

> Do NOT import `detect_document_type` here — `reprocess_document` must never call it (that is the whole point of the forced path), and an unused import would be stripped by the ruff `--fix` hook. The test asserts non-invocation by patching it at its source module, `app.services.extraction_engine.detect_document_type`.

Add the function:

```python
def reprocess_document(document_id: str, schema_id: str, db: Session) -> Document:
    """Re-extract a document against a forced schema, skipping type detection.

    Used after a schema proposal is applied: the operator already knows which
    schema this document should use, so re-running detection (which could
    re-classify it as OTHER) is wrong. Pins schema_id + detected_doc_type,
    clears prior extractions, and re-extracts from the stored ocr_text.
    """
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise ValueError(f"Document {document_id} not found")
    schema = db.query(DocumentSchema).filter(DocumentSchema.id == schema_id).first()
    if not schema:
        raise ValueError(f"Schema {schema_id} not found")
    if not doc.ocr_text:
        raise ValueError("Document has no ocr_text — cannot reprocess without source text")

    # Clear prior extractions so the document starts clean.
    db.query(DocumentExtraction).filter(
        DocumentExtraction.document_id == doc.id
    ).delete()

    # Pin the schema; do NOT run detection.
    doc.schema_id = schema.id
    doc.detected_doc_type = schema.document_type
    doc.extraction_error = None

    raw = extract_fields(doc.ocr_text, schema, doc.id, doc.workspace_id)
    save_extractions(raw, doc.id, doc.workspace_id, schema.id, db)

    if schema.parse_strategy == "claude" and schema.schema_fields and not raw:
        doc.extraction_status = "needs_review"
        doc.extraction_error = "Reprocess returned zero fields"
    else:
        doc.extraction_status = "complete"
    db.flush()

    audit.log(
        db,
        action="document_reprocessed",
        user_id=doc.uploaded_by,
        workspace_id=doc.workspace_id,
        entity_type="document",
        entity_id=doc.id,
        after_state={"schema_id": schema.id, "status": doc.extraction_status, "fields": len(raw)},
    )
    return doc
```

> `save_extractions` and `audit.log` each `commit()`; the final `audit.log` persists the status change and its audit row together.

- [ ] **Step 4: Run the tests to verify they pass**

Run:
```
docker-compose run --rm -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test backend pytest tests/test_schema_proposals.py -k reprocess -v --ignore=tests/evals
```
Expected: all three `reprocess` tests PASS.

- [ ] **Step 5: Run the full Phase 1 test file + the soft-delete hook sanity**

Run:
```
docker-compose run --rm -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test backend pytest tests/test_schema_proposals.py tests/test_documents.py tests/test_pipeline.py -v --ignore=tests/evals
```
Expected: all PASS (new file green; no regression in document/pipeline tests).

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/document_service.py backend/tests/test_schema_proposals.py
git commit -m "feat: reprocess_document forced-schema re-extraction"
```

---

## Self-Review

**Spec coverage (Phase 1 MoSCoW + Phase 1 details from the PRD):**
- `schema_change_proposals` table + lifecycle → Task 1 ✓ (status enum `draft|rejected|applied|failed`)
- Proposal provenance (model id, prompt version, inputs) → Task 1 ✓ (`model_id`, `prompt_version`, `proposer_inputs`)
- DB partial unique index + atomic supersession + `order_by(version.desc())` → Tasks 1, 2, 4 ✓
- Server-side `validate_proposal` (all eight rule classes) → Task 3 ✓
- Forced-schema reprocess (skip re-detection) → Task 5 ✓
- OCR precondition → enforced in Task 5 (`reprocess_document`); the *proposal-generation* OCR precondition is Phase 2 (`propose_schema_for_document`), correctly out of Phase 1 scope.
- Soft-delete columns on the new model → Task 1 ✓

**Deferred to Phase 2 (intentionally not here):** `propose_schema_for_document`, `apply_schema_proposal`, the create/apply/reject endpoints, owner-only role gating. Phase 1 ships no router and no AI calls — only the substrate they consume.

**Placeholder scan:** none — every step has concrete code and exact commands.

**Type consistency:** `validate_proposal(proposal, db) -> list[str]`, `supersede_schema(db, base, new_fields) -> DocumentSchema`, `reprocess_document(document_id, schema_id, db) -> Document` are referenced consistently across tasks and match the PRD's named service methods. `extract_fields`/`save_extractions` signatures match `extraction_engine.py`. Field dict keys (`name`/`type`/`description`/`confidence_threshold`) match the seed schema shape; extraction-row keys (`field_name`/`field_value`/…) match `save_extractions`.

**One known limitation (documented, not a gap):** `reprocess_document` re-extracts via the claude `extract_fields` path using stored `ocr_text`; it does not re-run the pipeline's confidence-retry evaluator or the `xml_direct` branch. That's acceptable for Phase 1 (the feature need is "force a known schema and get `complete`"); the evaluator loop remains owned by the full upload pipeline. Revisit if forced-reprocess of XML-direct docs becomes a requirement.

---

## Execution Handoff

See the prompt after this plan is saved for the two execution options.
