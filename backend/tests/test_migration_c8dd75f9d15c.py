"""Round-trip reversibility test for migration c8dd75f9d15c.

c8dd75f9d15c.downgrade() must restore the affected general schemas to their
canonical pre-cleanup seed values. The test drives c8dd's OWN upgrade()/downgrade()
against a connection inside a rolled-back transaction — it does NOT use
command.downgrade() to unwind the whole migration chain. Unwinding the chain is
both unnecessary (we only care about c8dd) and unsafe: at least one intervening
migration (e1ca59dae292) has an incomplete downgrade that orphans an enum type,
so a full-chain down/up round-trip fails for reasons unrelated to c8dd.

Isolation works by binding the migration's global `op` to an Operations context on
our connection (restored afterward), then rolling the transaction back so no state
persists. Expected values are read from the migration module's own constants, so
the assertions cannot drift from what downgrade() writes.
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

# Cleaned descriptions written by upgrade() — restored to originals by downgrade().
# Asserted to prove the upgrade-side cleaning actually fired before each round-trip.
_CLEANED_DESCRIPTIONS = {
    ("PARCEL-RECORD", "owner_occupied"): "Whether the property is owner-occupied.",
    (
        "990",
        "gov_related_entity",
    ): "IRS990/RelatedEntityInd — whether the organization has disclosed related entities.",
    ("SOS-FILING", "law_firm_filer"): "Name of law firm or attorney that submitted the filing.",
    (
        "BUILDING-PERMIT",
        "contractor_name",
    ): "Contractor or builder name — second part of the OWNER OR BUILDER field after the slash.",
    ("BUILDING-PERMIT", "estimated_value"): "Estimated construction value in dollars.",
}


def _field(name, description):
    return {"name": name, "type": "text", "description": description}


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


def _prompt(conn, document_type):
    return conn.execute(
        text("SELECT extraction_prompt FROM document_schemas WHERE document_type = :t").bindparams(
            t=document_type
        )
    ).scalar()


def _description(conn, document_type, field):
    return conn.execute(
        text("""
        SELECT elem->>'description'
        FROM document_schemas, jsonb_array_elements(schema_fields) AS elem
        WHERE document_type = :t AND elem->>'name' = :f
    """).bindparams(t=document_type, f=field)
    ).scalar()


def test_c8dd_downgrade_restores_canonical_values(test_engine):
    prompts = c8dd._ORIGINAL_PROMPTS  # {dtype: original prompt}
    descs = c8dd._ORIGINAL_DESCRIPTIONS  # {(dtype, field): original description}

    conn = test_engine.connect()
    trans = conn.begin()
    real_op = c8dd.op
    # Bind the migration's global `op` to THIS connection so upgrade()/downgrade()
    # run inside our transaction instead of against the live alembic chain.
    c8dd.op = Operations(MigrationContext.configure(conn))
    try:
        # Seed controlled pre-cleanup rows for EVERY surface upgrade() touches
        # (document_schemas is truncated by setup_db, so nothing else is present).
        _insert_schema(
            conn,
            document_type="OBITUARY",
            vertical="general",
            fields=[_field("deceased_name", "x")],
            prompt="obit prompt",
        )
        _insert_schema(
            conn,
            document_type="PARCEL-RECORD",
            vertical="general",
            fields=[_field("owner_occupied", descs[("PARCEL-RECORD", "owner_occupied")])],
            prompt="parcel prompt",
        )
        _insert_schema(
            conn,
            document_type="990",
            vertical="general",
            fields=[_field("gov_related_entity", descs[("990", "gov_related_entity")])],
            prompt=prompts["990"],
        )
        _insert_schema(
            conn,
            document_type="SOS-FILING",
            vertical="general",
            fields=[_field("law_firm_filer", descs[("SOS-FILING", "law_firm_filer")])],
            prompt="sos prompt",
        )
        _insert_schema(
            conn,
            document_type="UCC",
            vertical="general",
            fields=[_field("debtor_name", "x")],
            prompt=prompts["UCC"],
        )
        _insert_schema(
            conn,
            document_type="BUILDING-PERMIT",
            vertical="general",
            fields=[
                _field("contractor_name", descs[("BUILDING-PERMIT", "contractor_name")]),
                _field("estimated_value", descs[("BUILDING-PERMIT", "estimated_value")]),
            ],
            prompt=prompts["BUILDING-PERMIT"],
        )

        # --- Apply cleanup; assert every surface was actually cleaned. ---
        c8dd.upgrade()
        assert (
            conn.execute(
                text("SELECT vertical FROM document_schemas WHERE document_type='OBITUARY'")
            ).scalar()
            == "fraud"
        )
        for dtype in prompts:
            cleaned = _prompt(conn, dtype)
            assert "SR-0" not in cleaned, f"{dtype} prompt still has SR code after upgrade"
        # Guard against upgrade blanking the prompt entirely (loose substring check).
        assert "ReturnHeader" in _prompt(conn, "990")
        for (dtype, field), cleaned in _CLEANED_DESCRIPTIONS.items():
            assert _description(conn, dtype, field) == cleaned

        # --- Roll back via downgrade; assert canonical restoration of ALL surfaces. ---
        c8dd.downgrade()
        assert (
            conn.execute(
                text("SELECT vertical FROM document_schemas WHERE document_type='OBITUARY'")
            ).scalar()
            == "general"
        )
        for dtype, original in prompts.items():
            assert _prompt(conn, dtype) == original, f"{dtype} prompt not restored"
        for (dtype, field), original in descs.items():
            assert _description(conn, dtype, field) == original, (
                f"{dtype}/{field} description not restored"
            )
    finally:
        c8dd.op = real_op
        trans.rollback()
        conn.close()
