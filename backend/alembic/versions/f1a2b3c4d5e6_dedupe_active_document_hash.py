"""dedupe: unique active document by (workspace_id, sha256_hash)

Revision ID: f1a2b3c4d5e6
Revises: 3e34cdd125b6
Create Date: 2026-06-22

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f1a2b3c4d5e6"
down_revision: str | None = "3e34cdd125b6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Heal existing data first: a non-clean DB may already hold duplicate active
    # api_pull documents for the same (workspace_id, sha256_hash), which would make
    # CREATE UNIQUE INDEX fail and block the upgrade. Soft-delete all but the
    # earliest of each duplicate group so the partial unique index can be created.
    op.execute(
        sa.text(
            """
            WITH ranked AS (
                SELECT id,
                       ROW_NUMBER() OVER (
                           PARTITION BY workspace_id, sha256_hash ORDER BY uploaded_at, id
                       ) AS rn
                FROM documents
                WHERE is_deleted = false AND source_type = 'api_pull'
            )
            UPDATE documents d
            SET is_deleted = true, deleted_at = now()
            FROM ranked r
            WHERE d.id = r.id AND r.rn > 1
            """
        )
    )

    # Atomic dedup for CONNECTOR-sourced documents: at most one active
    # (non-deleted) api_pull document per (workspace_id, sha256_hash). Scoped to
    # source_type='api_pull' because manual uploads intentionally allow the same
    # content to be added more than once; only the connector path dedups by hash.
    # Partial WHERE is_deleted=false so a re-pull after a soft delete is allowed.
    # Enforces at the DB layer what the connector previously only checked in
    # application code, closing the check-then-insert race between fetch workers.
    op.create_index(
        "uq_documents_active_workspace_hash",
        "documents",
        ["workspace_id", "sha256_hash"],
        unique=True,
        postgresql_where=sa.text("is_deleted = false AND source_type = 'api_pull'"),
    )


def downgrade() -> None:
    op.drop_index("uq_documents_active_workspace_hash", table_name="documents")
