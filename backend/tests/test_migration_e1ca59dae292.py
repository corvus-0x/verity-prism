"""Round-trip reversibility test for migration e1ca59dae292.

upgrade() creates the schema_change_proposals table with two inline Enum columns,
which makes PostgreSQL create the `proposal_type` and `proposal_status` enum types.
downgrade() must drop those enum types too — not just the table — otherwise a
down -> up round-trip fails with `type "proposal_type" already exists`.

Isolated like test_migration_c8dd75f9d15c: drives the migration's own
downgrade()/upgrade() against a connection bound to its `op`, inside a rolled-back
transaction, so no state persists and the live alembic chain is untouched.
"""

import importlib.util
from pathlib import Path

from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from sqlalchemy import text

_MIG_PATH = (
    Path(__file__).resolve().parent.parent
    / "alembic"
    / "versions"
    / "e1ca59dae292_add_schema_change_proposals_table_and_.py"
)
_spec = importlib.util.spec_from_file_location("e1ca59_migration", _MIG_PATH)
e1ca = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(e1ca)


def _scalar(conn, sql):
    return conn.execute(text(sql)).scalar()


def _enum_exists(conn, name):
    return _scalar(conn, f"SELECT EXISTS (SELECT 1 FROM pg_type WHERE typname = '{name}')")


def test_e1ca59_downgrade_then_upgrade_round_trips(test_engine):
    conn = test_engine.connect()
    trans = conn.begin()
    real_op = e1ca.op
    e1ca.op = Operations(MigrationContext.configure(conn))
    try:
        # Preconditions at head: table + both enum types exist.
        assert _scalar(conn, "SELECT to_regclass('schema_change_proposals') IS NOT NULL")
        assert _enum_exists(conn, "proposal_type")
        assert _enum_exists(conn, "proposal_status")

        # Roll back: must drop the table AND both enum types.
        e1ca.downgrade()
        assert _scalar(conn, "SELECT to_regclass('schema_change_proposals') IS NULL")
        assert not _enum_exists(conn, "proposal_type"), "proposal_type enum orphaned by downgrade"
        assert not _enum_exists(conn, "proposal_status"), (
            "proposal_status enum orphaned by downgrade"
        )

        # Re-apply: this is the step that previously raised
        # 'type "proposal_type" already exists'.
        e1ca.upgrade()
        assert _scalar(conn, "SELECT to_regclass('schema_change_proposals') IS NOT NULL")
        assert _enum_exists(conn, "proposal_type")
        assert _enum_exists(conn, "proposal_status")
    finally:
        e1ca.op = real_op
        trans.rollback()
        conn.close()
