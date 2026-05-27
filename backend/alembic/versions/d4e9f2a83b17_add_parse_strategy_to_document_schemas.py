"""add_parse_strategy_to_document_schemas

Revision ID: d4e9f2a83b17
Revises: a3b8e1f92d44
Create Date: 2026-05-26

Adds parse_strategy (claude|xml_direct) and default_confidence_threshold
to document_schemas. parse_strategy controls whether the extraction engine
uses Claude or a direct XML parser. 990 and 990-T forms are structured XML
(IRS TEOS), so they get xml_direct with confidence 1.0 — no AI inference
needed when the data is machine-readable.
"""
from typing import Sequence, Union
from alembic import op


revision: str = 'd4e9f2a83b17'
down_revision: Union[str, None] = 'a3b8e1f92d44'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'parse_strategy') THEN
                CREATE TYPE parse_strategy AS ENUM ('claude', 'xml_direct');
            END IF;
        END $$;
    """)
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'document_schemas' AND column_name = 'parse_strategy'
            ) THEN
                ALTER TABLE document_schemas
                ADD COLUMN parse_strategy parse_strategy NOT NULL DEFAULT 'claude';
            END IF;
        END $$;
    """)
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'document_schemas' AND column_name = 'default_confidence_threshold'
            ) THEN
                ALTER TABLE document_schemas
                ADD COLUMN default_confidence_threshold FLOAT NOT NULL DEFAULT 0.7;
            END IF;
        END $$;
    """)
    op.execute("""
        UPDATE document_schemas
        SET parse_strategy = 'xml_direct',
            default_confidence_threshold = 1.0
        WHERE document_type IN ('990', '990-T');
    """)


def downgrade() -> None:
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'document_schemas' AND column_name = 'default_confidence_threshold'
            ) THEN
                ALTER TABLE document_schemas DROP COLUMN default_confidence_threshold;
            END IF;
        END $$;
    """)
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'document_schemas' AND column_name = 'parse_strategy'
            ) THEN
                ALTER TABLE document_schemas DROP COLUMN parse_strategy;
            END IF;
        END $$;
    """)
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_type WHERE typname = 'parse_strategy') THEN
                DROP TYPE parse_strategy;
            END IF;
        END $$;
    """)
