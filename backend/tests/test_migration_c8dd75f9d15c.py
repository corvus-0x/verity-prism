"""Round-trip reversibility test for migration c8dd75f9d15c.

c8dd75f9d15c.downgrade() must restore the affected general schemas to their
canonical pre-cleanup seed values. The test drives c8dd's OWN upgrade()/downgrade()
against a connection inside a rolled-back transaction — it does NOT use
command.downgrade() to unwind the whole migration chain. Unwinding the chain is
both unnecessary (we only care about c8dd) and unsafe: at least one intervening
migration (e1ca59dae292) has an incomplete downgrade that orphans an enum type,
so a full-chain down/up round-trip fails for reasons unrelated to c8dd.

Isolation works by binding the migration's global `op` to an Operations context on
our connection, then rolling the transaction back so no state persists.
"""

import importlib.util
import json
import uuid
from pathlib import Path

from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from sqlalchemy import text

# Import the migration module to (a) call its upgrade()/downgrade() and (b) read
# its canonical constants, so the test and migration cannot drift.
_MIG_PATH = (
    Path(__file__).resolve().parent.parent
    / "alembic"
    / "versions"
    / "c8dd75f9d15c_schema_cleanup_obituary_and_sr_.py"
)
_spec = importlib.util.spec_from_file_location("c8dd_migration", _MIG_PATH)
c8dd = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(c8dd)


def _insert_schema(conn, *, document_type, vertical, fields, prompt):
    """Insert one controlled document_schemas row with every NOT NULL column set."""
    conn.execute(
        text("""
            INSERT INTO document_schemas
                (id, document_type, vertical, display_name, schema_fields,
                 extraction_prompt, version, is_active, parse_strategy,
                 default_confidence_threshold, created_at)
            VALUES
                (:id, :t, :v, :dn, CAST(:sf AS jsonb), :ep,
                 1, true, 'claude', 0.7, now())
        """).bindparams(
            id=str(uuid.uuid4()),
            t=document_type,
            v=vertical,
            dn=document_type,
            sf=json.dumps(fields),
            ep=prompt,
        )
    )


def _description(conn, document_type, field):
    return conn.execute(
        text("""
        SELECT elem->>'description'
        FROM document_schemas, jsonb_array_elements(schema_fields) AS elem
        WHERE document_type = :t AND elem->>'name' = :f
    """).bindparams(t=document_type, f=field)
    ).scalar()


def test_c8dd_downgrade_restores_canonical_values(test_engine):
    orig_990_prompt = c8dd._ORIGINAL_PROMPTS["990"]
    orig_est_desc = c8dd._ORIGINAL_DESCRIPTIONS[("BUILDING-PERMIT", "estimated_value")]

    conn = test_engine.connect()
    trans = conn.begin()
    # Bind the migration's global `op` to THIS connection so upgrade()/downgrade()
    # run inside our transaction instead of against the live alembic chain.
    c8dd.op = Operations(MigrationContext.configure(conn))
    try:
        # Seed controlled pre-cleanup rows (document_schemas is truncated by setup_db).
        _insert_schema(
            conn,
            document_type="OBITUARY",
            vertical="general",
            fields=[{"name": "deceased_name", "type": "name", "description": "x"}],
            prompt="obit prompt",
        )
        _insert_schema(
            conn,
            document_type="990",
            vertical="general",
            fields=[{"name": "gov_related_entity", "type": "boolean", "description": "x"}],
            prompt=orig_990_prompt,
        )
        _insert_schema(
            conn,
            document_type="BUILDING-PERMIT",
            vertical="general",
            fields=[{"name": "estimated_value", "type": "currency", "description": orig_est_desc}],
            prompt="permit prompt",
        )

        # Apply cleanup, assert all three surfaces cleaned.
        c8dd.upgrade()
        assert (
            conn.execute(
                text("SELECT vertical FROM document_schemas WHERE document_type='OBITUARY'")
            ).scalar()
            == "fraud"
        )
        assert (
            "SR-0"
            not in conn.execute(
                text("SELECT extraction_prompt FROM document_schemas WHERE document_type='990'")
            ).scalar()
        )
        assert (
            _description(conn, "BUILDING-PERMIT", "estimated_value")
            == "Estimated construction value in dollars."
        )

        # Roll back via downgrade, assert canonical restoration of all three surfaces.
        c8dd.downgrade()
        assert (
            conn.execute(
                text("SELECT vertical FROM document_schemas WHERE document_type='OBITUARY'")
            ).scalar()
            == "general"
        )
        assert (
            conn.execute(
                text("SELECT extraction_prompt FROM document_schemas WHERE document_type='990'")
            ).scalar()
            == orig_990_prompt
        )
        assert _description(conn, "BUILDING-PERMIT", "estimated_value") == orig_est_desc
    finally:
        trans.rollback()
        conn.close()
