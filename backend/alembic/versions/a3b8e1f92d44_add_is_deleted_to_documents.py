"""add_is_deleted_to_documents

Revision ID: a3b8e1f92d44
Revises: c12f44824c55
Create Date: 2026-05-26

Adds is_deleted and deleted_at columns to documents table for soft-delete
support, consistent with the soft-delete convention used on entities.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = 'a3b8e1f92d44'
down_revision: Union[str, None] = 'c12f44824c55'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'documents'
                AND column_name = 'is_deleted'
            ) THEN
                ALTER TABLE documents ADD COLUMN is_deleted BOOLEAN NOT NULL DEFAULT FALSE;
            END IF;
        END $$;
    """)
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'documents'
                AND column_name = 'deleted_at'
            ) THEN
                ALTER TABLE documents ADD COLUMN deleted_at TIMESTAMPTZ;
            END IF;
        END $$;
    """)


def downgrade() -> None:
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'documents'
                AND column_name = 'deleted_at'
            ) THEN
                ALTER TABLE documents DROP COLUMN deleted_at;
            END IF;
        END $$;
    """)
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'documents'
                AND column_name = 'is_deleted'
            ) THEN
                ALTER TABLE documents DROP COLUMN is_deleted;
            END IF;
        END $$;
    """)
