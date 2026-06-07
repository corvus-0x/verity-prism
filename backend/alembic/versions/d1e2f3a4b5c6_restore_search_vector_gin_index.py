"""restore search_vector GIN index

Migration 50f2b84a06aa (workspace render mode) auto-dropped
idx_documents_search_vector because the index was created via raw SQL
in a1b2c3d4e5f6 and was invisible to Alembic's metadata comparison.
This migration recreates it and the model now declares it explicitly
so autogenerate will never drop it again.

Revision ID: d1e2f3a4b5c6
Revises: cf7d3b604763
Create Date: 2026-06-02
"""
from typing import Sequence, Union

from alembic import op

revision: str = "d1e2f3a4b5c6"
down_revision: Union[str, None] = "cf7d3b604763"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "idx_documents_search_vector",
        "documents",
        ["search_vector"],
        unique=False,
        postgresql_using="gin",
    )


def downgrade() -> None:
    op.drop_index("idx_documents_search_vector", table_name="documents")
