"""add_no_schema_status_and_extraction_error

Revision ID: c12f44824c55
Revises: 5a4ff7266708
Create Date: 2026-05-20

Adds 'no_schema' to the extraction_status enum and the extraction_error
column to documents. These were applied directly to the live DB in Task 8
but were missing from migrations — this makes clean rebuilds work correctly.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = 'c12f44824c55'
down_revision: Union[str, None] = '5a4ff7266708'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add 'no_schema' to the extraction_status enum.
    # IF NOT EXISTS prevents failure when running against the live DB
    # where the value was already added directly.
    op.execute("ALTER TYPE extraction_status ADD VALUE IF NOT EXISTS 'no_schema'")

    # Add extraction_error column — idempotent check so this is safe to run
    # against a DB where the column already exists.
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'documents'
                AND column_name = 'extraction_error'
            ) THEN
                ALTER TABLE documents ADD COLUMN extraction_error VARCHAR;
            END IF;
        END $$;
    """)


def downgrade() -> None:
    # Remove the extraction_error column if it exists.
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'documents'
                AND column_name = 'extraction_error'
            ) THEN
                ALTER TABLE documents DROP COLUMN extraction_error;
            END IF;
        END $$;
    """)
    # Note: PostgreSQL does not support removing enum values without recreating
    # the type. The 'no_schema' value will remain in the enum after downgrade.
    # To fully revert, drop and recreate the enum — see initial migration.
