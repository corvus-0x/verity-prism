"""add_pgvector_embedding

Revision ID: cf7d3b604763
Revises: 50f2b84a06aa
Create Date: 2026-06-01 20:46:32.670812

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'cf7d3b604763'
down_revision: Union[str, None] = '50f2b84a06aa'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("ALTER TABLE documents ADD COLUMN IF NOT EXISTS embedding vector(1536)")
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_documents_embedding_ivfflat "
        "ON documents USING ivfflat (embedding vector_cosine_ops) "
        "WITH (lists = 100)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_documents_embedding_ivfflat")
    op.execute("ALTER TABLE documents DROP COLUMN IF EXISTS embedding")
