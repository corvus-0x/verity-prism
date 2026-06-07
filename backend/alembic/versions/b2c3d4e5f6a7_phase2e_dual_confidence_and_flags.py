"""phase2e_dual_confidence_and_flags

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-05-30

Adds:
- ocr_confidence to document_extractions (Claude's estimate of source text clarity)
- flag_reason and flag_note to documents (structured reviewer rejection feedback)
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'document_extractions'
                AND column_name = 'ocr_confidence'
            ) THEN
                ALTER TABLE document_extractions
                    ADD COLUMN ocr_confidence FLOAT NOT NULL DEFAULT 1.0;
            END IF;
        END $$;
    """)

    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'documents'
                AND column_name = 'flag_reason'
            ) THEN
                ALTER TABLE documents ADD COLUMN flag_reason VARCHAR;
                ALTER TABLE documents ADD COLUMN flag_note TEXT;
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
                AND column_name = 'ocr_confidence'
            ) THEN
                ALTER TABLE document_extractions DROP COLUMN ocr_confidence;
            END IF;
        END $$;
    """)
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'documents'
                AND column_name = 'flag_reason'
            ) THEN
                ALTER TABLE documents DROP COLUMN flag_reason;
                ALTER TABLE documents DROP COLUMN flag_note;
            END IF;
        END $$;
    """)
