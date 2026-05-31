"""review_pane_evidence

Revision ID: d5e6f7a8b9c0
Revises: b2c3d4e5f6a7
Create Date: 2026-05-31

Adds evidence JSONB to document_extractions for PDF region capture data.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = 'd5e6f7a8b9c0'
down_revision: Union[str, None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'document_extractions'
                AND column_name = 'evidence'
            ) THEN
                ALTER TABLE document_extractions ADD COLUMN evidence JSONB;
            END IF;
        END $$;
    """)


def downgrade() -> None:
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'document_extractions'
                AND column_name = 'evidence'
            ) THEN
                ALTER TABLE document_extractions DROP COLUMN evidence;
            END IF;
        END $$;
    """)
