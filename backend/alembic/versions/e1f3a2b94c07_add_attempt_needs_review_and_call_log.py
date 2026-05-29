"""add_attempt_needs_review_and_call_log

Revision ID: e1f3a2b94c07
Revises: c8dd75f9d15c
Create Date: 2026-05-28

Adds:
- attempt column to document_extractions (tracks initial extract vs retry vs human correction)
- needs_review value to extraction_status enum
- claude_call_logs table for extraction observability
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = 'e1f3a2b94c07'
down_revision: Union[str, None] = 'c8dd75f9d15c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add attempt column — server_default='1' so existing rows populate correctly
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'document_extractions'
                AND column_name = 'attempt'
            ) THEN
                ALTER TABLE document_extractions
                    ADD COLUMN attempt INTEGER NOT NULL DEFAULT 1;
            END IF;
        END $$;
    """)

    # Add needs_review to extraction_status enum
    op.execute("ALTER TYPE extraction_status ADD VALUE IF NOT EXISTS 'needs_review'")

    # Create claude_call_logs table
    op.execute("""
        CREATE TABLE IF NOT EXISTS claude_call_logs (
            id VARCHAR PRIMARY KEY,
            call_type VARCHAR NOT NULL,
            document_id VARCHAR,
            workspace_id VARCHAR,
            schema_id VARCHAR,
            model VARCHAR NOT NULL,
            attempt INTEGER,
            success BOOLEAN NOT NULL DEFAULT TRUE,
            latency_ms INTEGER NOT NULL,
            input_tokens INTEGER,
            output_tokens INTEGER,
            prompt_chars INTEGER NOT NULL,
            response_chars INTEGER,
            error_message VARCHAR,
            called_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
        );
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_call_log_document_id
            ON claude_call_logs(document_id);
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_call_log_called_at
            ON claude_call_logs(called_at);
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS claude_call_logs")
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'document_extractions'
                AND column_name = 'attempt'
            ) THEN
                ALTER TABLE document_extractions DROP COLUMN attempt;
            END IF;
        END $$;
    """)
    # PostgreSQL cannot remove enum values — needs_review remains in the type after downgrade
