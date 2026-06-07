# Schema Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the OBITUARY schema to the fraud vertical, and remove SR signal code references and explicit fraud investigation commentary from the nine general-purpose schemas so they read as neutral IDP infrastructure, not fraud investigation tools.

**Architecture:** Two independent changes. (1) OBITUARY is moved from `vertical="general"` to `vertical="fraud"` via a migration that updates the existing DB row, plus a seed file update for fresh installs. (2) Field descriptions and extraction prompts in the nine remaining general schemas are cleaned of signal codes (SR-XXX) and fraud-specific commentary via a seed file update for fresh installs plus a migration that applies the same changes to existing DB rows using PostgreSQL JSONB operations and text column updates.

**Tech Stack:** Python 3.12, SQLAlchemy 2.0, Alembic, PostgreSQL 16, pytest

**Order:** Run this plan after `2026-05-26-idp-expansion-architecture.md` is complete, so the migration chain is intact.

---

## File Map

| File | Status | Change |
|------|--------|--------|
| `backend/alembic/versions/<id>_schema_cleanup.py` | CREATE | Move OBITUARY to fraud; clean SR references in DB |
| `backend/app/seeds/document_schemas.py` | MODIFY | Update OBITUARY vertical; remove SR references from descriptions/prompts |
| `backend/tests/test_extractions.py` | MODIFY | Test that OBITUARY is fraud-vertical; general workspaces don't receive it |

---

## Task 1: Move OBITUARY to vertical="fraud"

**Files:**
- Create: `backend/alembic/versions/<id>_schema_cleanup.py`
- Modify: `backend/app/seeds/document_schemas.py`
- Modify: `backend/tests/test_extractions.py`

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_extractions.py`:

```python
from app.services.extraction_engine import get_schema_for_type


def test_obituary_schema_not_available_in_general_workspace(db):
    """OBITUARY is fraud-vertical only — general workspaces should not receive it."""
    result = get_schema_for_type("OBITUARY", db, workspace_vertical="general")
    assert result is None


def test_obituary_schema_available_in_fraud_workspace(db):
    """OBITUARY schema is available in fraud workspaces."""
    from app.models.document_schema import DocumentSchema
    import uuid
    # Seed a fraud-vertical OBITUARY schema directly in the test
    schema = DocumentSchema(
        id=str(uuid.uuid4()),
        document_type="OBITUARY",
        display_name="Obituary",
        vertical="fraud",
        schema_fields=[{"name": "deceased_full_name", "type": "name", "description": "Full name", "required": True}],
        version=1,
        is_active=True,
        parse_strategy="claude",
        default_confidence_threshold=0.75,
    )
    db.add(schema)
    db.commit()

    result = get_schema_for_type("OBITUARY", db, workspace_vertical="fraud")
    assert result is not None
    assert result.vertical == "fraud"
```

- [ ] **Step 2: Run to confirm they fail**

```bash
cd backend
pytest tests/test_extractions.py::test_obituary_schema_not_available_in_general_workspace -v
```

Expected: FAIL — OBITUARY schema currently has `vertical="general"` so `get_schema_for_type` returns it for general workspaces.

- [ ] **Step 3: Generate the migration**

```bash
cd backend
alembic revision -m "schema_cleanup_obituary_and_sr_references"
```

Open the new file and add this upgrade/downgrade:

```python
from alembic import op
from sqlalchemy import text


def upgrade() -> None:
    # Move OBITUARY to fraud vertical
    op.execute("""
        UPDATE document_schemas
        SET vertical = 'fraud'
        WHERE document_type = 'OBITUARY';
    """)

    # Remove SR signal code references from 990 extraction_prompt
    op.execute("""
        UPDATE document_schemas
        SET extraction_prompt = REGEXP_REPLACE(
            extraction_prompt,
            ' ?\\(?SR-0[0-9]+\\)?',
            '',
            'g'
        )
        WHERE document_type = '990' AND vertical = 'general';
    """)

    # Remove SR signal code references from UCC extraction_prompt
    op.execute("""
        UPDATE document_schemas
        SET extraction_prompt = REGEXP_REPLACE(
            extraction_prompt,
            ' ?\\(?SR-0[0-9]+\\)?',
            '',
            'g'
        )
        WHERE document_type = 'UCC' AND vertical = 'general';
    """)

    # Remove SR signal code references from BUILDING-PERMIT extraction_prompt
    op.execute("""
        UPDATE document_schemas
        SET extraction_prompt = REGEXP_REPLACE(
            extraction_prompt,
            ' ?\\(?SR-0[0-9]+\\)?',
            '',
            'g'
        )
        WHERE document_type = 'BUILDING-PERMIT' AND vertical = 'general';
    """)

    # Clean owner_occupied field description in PARCEL-RECORD
    op.execute("""
        UPDATE document_schemas
        SET schema_fields = (
            SELECT jsonb_agg(
                CASE
                    WHEN elem->>'name' = 'owner_occupied'
                    THEN elem || '{"description": "Whether the property is owner-occupied."}'::jsonb
                    ELSE elem
                END
            )
            FROM jsonb_array_elements(schema_fields) AS elem
        )
        WHERE document_type = 'PARCEL-RECORD' AND vertical = 'general';
    """)

    # Clean gov_related_entity description in 990
    op.execute("""
        UPDATE document_schemas
        SET schema_fields = (
            SELECT jsonb_agg(
                CASE
                    WHEN elem->>'name' = 'gov_related_entity'
                    THEN elem || '{"description": "IRS990/RelatedEntityInd — whether the organization has disclosed related entities."}'::jsonb
                    ELSE elem
                END
            )
            FROM jsonb_array_elements(schema_fields) AS elem
        )
        WHERE document_type = '990' AND vertical = 'general';
    """)

    # Clean law_firm_filer description in SOS-FILING
    op.execute("""
        UPDATE document_schemas
        SET schema_fields = (
            SELECT jsonb_agg(
                CASE
                    WHEN elem->>'name' = 'law_firm_filer'
                    THEN elem || '{"description": "Name of law firm or attorney that submitted the filing."}'::jsonb
                    ELSE elem
                END
            )
            FROM jsonb_array_elements(schema_fields) AS elem
        )
        WHERE document_type = 'SOS-FILING' AND vertical = 'general';
    """)

    # Clean contractor_name description in BUILDING-PERMIT
    op.execute("""
        UPDATE document_schemas
        SET schema_fields = (
            SELECT jsonb_agg(
                CASE
                    WHEN elem->>'name' = 'contractor_name'
                    THEN elem || '{"description": "Contractor or builder name — second part of the OWNER OR BUILDER field after the slash."}'::jsonb
                    ELSE elem
                END
            )
            FROM jsonb_array_elements(schema_fields) AS elem
        )
        WHERE document_type = 'BUILDING-PERMIT' AND vertical = 'general';
    """)

    # Clean estimated_value description in BUILDING-PERMIT
    op.execute("""
        UPDATE document_schemas
        SET schema_fields = (
            SELECT jsonb_agg(
                CASE
                    WHEN elem->>'name' = 'estimated_value'
                    THEN elem || '{"description": "Estimated construction value in dollars."}'::jsonb
                    ELSE elem
                END
            )
            FROM jsonb_array_elements(schema_fields) AS elem
        )
        WHERE document_type = 'BUILDING-PERMIT' AND vertical = 'general';
    """)


def downgrade() -> None:
    # Move OBITUARY back to general
    op.execute("""
        UPDATE document_schemas
        SET vertical = 'general'
        WHERE document_type = 'OBITUARY';
    """)
    # Note: extraction_prompt and description restores are not implemented.
    # Re-seed from app/seeds/document_schemas.py if needed.
```

- [ ] **Step 4: Apply the migration**

```bash
cd backend
alembic upgrade head
```

Expected: migration applies without errors.

- [ ] **Step 5: Run the new tests**

```bash
cd backend
pytest tests/test_extractions.py -k "obituary" -v
```

Expected: both obituary tests PASS.

- [ ] **Step 6: Update seed_obituary_schema in the seed file**

In `backend/app/seeds/document_schemas.py`, in `seed_obituary_schema()`, change:
```python
# OLD
vertical="general",
# NEW
vertical="fraud",
```

- [ ] **Step 7: Run full test suite**

```bash
cd backend
pytest tests/ -v --tb=short 2>&1 | tail -5
```

Expected: all tests pass.

- [ ] **Step 8: Commit**

```bash
git add backend/alembic/versions/ backend/app/seeds/document_schemas.py backend/tests/test_extractions.py
git commit -m "fix: OBITUARY moved to fraud vertical; SR signal codes removed from general schema descriptions"
```

---

## Task 2: Clean remaining fraud commentary from seed file descriptions and prompts

**Files:**
- Modify: `backend/app/seeds/document_schemas.py`

The migration in Task 1 handled the existing DB rows. This task updates the seed file so fresh installs also get clean descriptions. No new migration needed — the seed file changes are for new installs only, and existing installs were already updated by the Task 1 migration.

- [ ] **Step 1: Clean PARCEL-RECORD field descriptions**

In `backend/app/seeds/document_schemas.py`, find and update these field definitions:

**`owner_occupied`** (in the LEGAL section):
```python
# OLD
{"name": "owner_occupied", "type": "boolean", "description": "Whether the property is owner-occupied. N on a nonprofit-owned residential property is a signal.", "required": False},
# NEW
{"name": "owner_occupied", "type": "boolean", "description": "Whether the property is owner-occupied.", "required": False},
```

**`tax_penalty_interest`** (in the TAX_CURRENT section):
```python
# OLD
{"name": "tax_penalty_interest", "type": "currency", "description": "Penalty and interest — non-zero signals delinquency", "required": False},
# NEW
{"name": "tax_penalty_interest", "type": "currency", "description": "Penalty and interest on unpaid taxes.", "required": False},
```

- [ ] **Step 2: Clean 990 field description and extraction prompt**

**`gov_related_entity`** field description:
```python
# OLD
{"name": "gov_related_entity", "type": "boolean", "description": "IRS990/RelatedEntityInd — does org have related entities? False when known related entities exist = SR-025 signal", "required": False},
# NEW
{"name": "gov_related_entity", "type": "boolean", "description": "IRS990/RelatedEntityInd — whether the organization has disclosed related entities.", "required": False},
```

In `EXTRACTION_PROMPT_990` (the string assigned to `extraction_prompt` for 990 schemas), remove the two signal-code references:
- Remove the line containing `SR-025` from the prompt
- Remove the line containing `FALSE DISCLOSURE signal`
- Remove any line beginning with `- RelatedEntityInd = false when known related entities exist`

Keep the analytical hints that help extraction accuracy (e.g., "$0 compensation for officers" as a note to look carefully). Only remove explicit signal code references.

- [ ] **Step 3: Clean SOS-FILING field description**

**`law_firm_filer`**:
```python
# OLD
{"name": "law_firm_filer", "type": "text", "description": "Name of law firm or attorney that submitted the filing — repeated appearance of same firm across entities is a network signal", "required": False},
# NEW
{"name": "law_firm_filer", "type": "text", "description": "Name of law firm or attorney that submitted the filing.", "required": False},
```

In the SOS-FILING extraction prompt, remove the sentence:
> "Repeated appearance of the same law firm across multiple entity filings is a network connection signal."

- [ ] **Step 4: Clean BUILDING-PERMIT field descriptions and extraction prompt**

**`contractor_name`**:
```python
# OLD
{"name": "contractor_name", "type": "name", "description": "Contractor or builder name — second part of the OWNER OR BUILDER field after the slash. Repeated appearance of the same contractor across an entity's permits is a network signal.", "required": False},
# NEW
{"name": "contractor_name", "type": "name", "description": "Contractor or builder name — second part of the OWNER OR BUILDER field after the slash.", "required": False},
```

**`estimated_value`**:
```python
# OLD
{"name": "estimated_value", "type": "currency", "description": "Estimated construction value in dollars. Compare to organization's annual revenue to detect SR-026 CONSTRUCTION_OVERAGE signal.", "required": False},
# NEW
{"name": "estimated_value", "type": "currency", "description": "Estimated construction value in dollars.", "required": False},
```

In the BUILDING-PERMIT extraction prompt, remove the lines referencing `SR-026 CONSTRUCTION_OVERAGE signal` and the comparison to organization revenue. Keep the note that `estimated_value` is the total declared construction cost.

- [ ] **Step 5: Clean UCC extraction prompt**

In the UCC extraction prompt, remove any reference to `SR-004` or `UCC_BURST signal`. Keep the factual description of what the time fields are used for (timestamping sequential filings). The analytical purpose description is fine; the signal code is not.

- [ ] **Step 6: Verify the seed file compiles**

```bash
cd backend
python -c "
from app.seeds.document_schemas import (
    seed_parcel_record_schema, seed_deed_schema, seed_990_schema,
    seed_ucc_schema, seed_building_permit_schema, seed_sos_filing_schema
)
print('All cleaned seed functions import OK')
"
```

Expected: prints `All cleaned seed functions import OK` with no errors.

- [ ] **Step 7: Run full test suite**

```bash
cd backend
pytest tests/ -v --tb=short 2>&1 | tail -5
```

Expected: all tests pass.

- [ ] **Step 8: Commit**

```bash
git add backend/app/seeds/document_schemas.py
git commit -m "fix: remove SR signal codes and fraud commentary from general schema descriptions and prompts"
```

---

## Self-Review

**Spec coverage:**

| Requirement | Task |
|-------------|------|
| OBITUARY moved to `vertical="fraud"` in DB | Task 1 migration |
| OBITUARY seed updated for fresh installs | Task 1 seed update |
| `get_schema_for_type("OBITUARY", general)` returns None | Task 1 test |
| `get_schema_for_type("OBITUARY", fraud)` returns schema | Task 1 test |
| SR signal codes removed from 990, UCC, BUILDING-PERMIT prompts | Task 1 migration + Task 2 seed |
| Investigation commentary removed from field descriptions | Task 1 migration + Task 2 seed |
| Fresh install seed matches cleaned state | Task 2 |

**Placeholder scan:** No TBDs or incomplete code blocks. ✓

**Downgrade note:** The downgrade only reverts OBITUARY. The description/prompt cleanup downgrade is not implemented because restoring exact original strings would require storing them in the migration, which is impractical. If needed, re-seed from the original seed file state via git history.
