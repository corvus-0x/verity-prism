"""phase2f connectors provenance

Revision ID: 45d36706d164
Revises: d5e6f7a8b9c0
Create Date: 2026-05-31 23:57:33.123456

Adds the connector_runs table (tracks each connector ingestion run) and a
source_ref column on documents (points back to the ConnectorRun that produced
the doc; null for uploads).
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = '45d36706d164'
down_revision: Union[str, None] = 'd5e6f7a8b9c0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'connector_runs',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('workspace_id', sa.String(), nullable=False),
        sa.Column('connector_id', sa.String(), nullable=False),
        sa.Column('search_query', sa.String(), nullable=True),
        sa.Column('candidate_label', sa.String(), nullable=True),
        sa.Column('params', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('result', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('error_message', sa.String(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_connector_runs_workspace_id'), 'connector_runs', ['workspace_id'], unique=False)
    op.add_column('documents', sa.Column('source_ref', sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column('documents', 'source_ref')
    op.drop_index(op.f('ix_connector_runs_workspace_id'), table_name='connector_runs')
    op.drop_table('connector_runs')
