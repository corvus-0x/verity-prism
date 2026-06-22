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
