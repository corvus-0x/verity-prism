"""phase4_search_integrity_soft_delete

H2: Change search_vector from TEXT to TSVECTOR and add GIN index.
L5: Add is_deleted / deleted_at to transactions, findings, investigation_leads,
    notes, and relationships.

Revision ID: a1b2c3d4e5f6
Revises: 3f29a7ad2392
Create Date: 2026-05-30
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "3f29a7ad2392"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SOFT_DELETE_TABLES = [
    "transactions",
    "findings",
    "investigation_leads",
    "notes",
    "relationships",
]


def upgrade() -> None:
    conn = op.get_bind()

    # H2 — fix search_vector column type (idempotent: skip if already TSVECTOR)
    col_type = conn.execute(sa.text(
        "SELECT data_type FROM information_schema.columns "
        "WHERE table_name = 'documents' AND column_name = 'search_vector'"
    )).scalar()
    if col_type and col_type.lower() != "tsvector":
        op.execute(
            "ALTER TABLE documents "
            "ALTER COLUMN search_vector TYPE TSVECTOR "
            "USING search_vector::tsvector"
        )

    # H2 — GIN index (idempotent)
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_documents_search_vector "
        "ON documents USING gin (search_vector)"
    )

    # L5 — extend soft-delete pattern to remaining entity tables (idempotent)
    for table in _SOFT_DELETE_TABLES:
        existing = conn.execute(sa.text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = :t AND column_name = 'is_deleted'"
        ), {"t": table}).scalar()
        if not existing:
            op.add_column(
                table,
                sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default="false"),
            )
            op.add_column(
                table,
                sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            )


def downgrade() -> None:
    # L5 — remove soft-delete columns
    for table in reversed(_SOFT_DELETE_TABLES):
        op.drop_column(table, "deleted_at")
        op.drop_column(table, "is_deleted")

    # H2 — revert TSVECTOR to TEXT
    op.drop_index("idx_documents_search_vector", table_name="documents")
    op.execute(
        "ALTER TABLE documents "
        "ALTER COLUMN search_vector TYPE TEXT "
        "USING search_vector::text"
    )
