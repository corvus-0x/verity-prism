"""seed signal_types reference data

Revision ID: f2b3c4d5e6f7
Revises: f1a2b3c4d5e6
Create Date: 2026-06-22

Moves signal-type seeding out of an on-read count()==0 guard (which had a
startup race window) into a one-time, idempotent data migration. ON CONFLICT on
the unique `code` makes it safe to apply to databases already seeded by the old
on-read path.
"""

import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert as pg_insert

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f2b3c4d5e6f7"
down_revision: str | None = "f1a2b3c4d5e6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


SIGNAL_TYPES_SEED = [
    {
        "code": "SR-003",
        "name": "VALUATION_ANOMALY",
        "description": "Property purchased significantly above or below appraised value",
        "severity": "critical",
        "relevant_to": ["AG", "IRS"],
    },
    {
        "code": "SR-004",
        "name": "UCC_BURST",
        "description": "Multiple UCC amendments filed within minutes — coordinated lien activity",
        "severity": "high",
        "relevant_to": ["FCA", "FBI"],
    },
    {
        "code": "SR-005",
        "name": "ZERO_CONSIDERATION",
        "description": "Property transferred for $0 to a private party",
        "severity": "critical",
        "relevant_to": ["AG", "IRS"],
    },
    {
        "code": "SR-015",
        "name": "DEED_TITLE_DEFECT",
        "description": "Deed executed in favor of an entity that did not legally exist at the time",
        "severity": "high",
        "relevant_to": ["AG"],
    },
    {
        "code": "SR-021",
        "name": "REVENUE_SPIKE",
        "description": "Organization revenue increased more than 500% year-over-year",
        "severity": "medium",
        "relevant_to": ["IRS"],
    },
    {
        "code": "SR-024",
        "name": "CHARITY_CONDUIT",
        "description": "Charitable funds used to fund improvements on privately-owned property",
        "severity": "critical",
        "relevant_to": ["IRS", "AG", "FBI"],
    },
    {
        "code": "SR-025",
        "name": "FALSE_DISCLOSURE",
        "description": "Organization disclosed related-party transactions in one year then denied them in all subsequent years while transactions continued",
        "severity": "critical",
        "relevant_to": ["IRS", "AG"],
    },
    {
        "code": "SR-026",
        "name": "CONSTRUCTION_OVERAGE",
        "description": "Construction permit value exceeds total organization revenue for that period",
        "severity": "high",
        "relevant_to": ["IRS", "AG"],
    },
]

_signal_types = sa.table(
    "signal_types",
    sa.column("id", sa.String),
    sa.column("code", sa.String),
    sa.column("name", sa.String),
    sa.column("description", sa.String),
    sa.column("severity", sa.String),
    sa.column("relevant_to", sa.ARRAY(sa.String)),
)


def upgrade() -> None:
    bind = op.get_bind()
    for s in SIGNAL_TYPES_SEED:
        stmt = (
            pg_insert(_signal_types)
            .values(id=str(uuid.uuid4()), **s)
            .on_conflict_do_nothing(index_elements=["code"])
        )
        bind.execute(stmt)


def downgrade() -> None:
    codes = tuple(s["code"] for s in SIGNAL_TYPES_SEED)
    op.execute(
        sa.text("DELETE FROM signal_types WHERE code IN :codes").bindparams(
            sa.bindparam("codes", value=codes, expanding=True)
        )
    )
