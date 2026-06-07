"""schema_cleanup_obituary_and_sr_references

Revision ID: c8dd75f9d15c
Revises: d4e9f2a83b17
Create Date: 2026-05-27 02:27:53.540527

Moves OBITUARY to the fraud vertical (it is a fraud investigation tool, not a
general IDP feature) and removes SR signal code references from general schema
extraction_prompts and field descriptions (those codes belong in the fraud
vertical cap, not general schema definitions).
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'c8dd75f9d15c'
down_revision: Union[str, None] = 'd4e9f2a83b17'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Move OBITUARY to fraud vertical — it's a fraud investigation tool, not a general IDP feature
    op.execute("""
        UPDATE document_schemas
        SET vertical = 'fraud'
        WHERE document_type = 'OBITUARY';
    """)

    # Remove SR signal code references from extraction_prompts
    # These signal codes (SR-XXX) belong in the fraud vertical cap, not general schema definitions
    op.execute("""
        UPDATE document_schemas
        SET extraction_prompt = REGEXP_REPLACE(
            extraction_prompt,
            ' ?\\(?SR-0[0-9]+\\)?',
            '',
            'g'
        )
        WHERE document_type IN ('990', 'UCC', 'BUILDING-PERMIT')
        AND vertical = 'general'
        AND extraction_prompt IS NOT NULL;
    """)

    # Clean owner_occupied field description in PARCEL-RECORD
    op.execute("""
        UPDATE document_schemas
        SET schema_fields = (
            SELECT jsonb_agg(
                CASE
                    WHEN elem->>'name' = 'owner_occupied'
                    THEN jsonb_set(elem, '{description}', '"Whether the property is owner-occupied."')
                    ELSE elem
                END
            )
            FROM jsonb_array_elements(schema_fields) AS elem
        )
        WHERE document_type = 'PARCEL-RECORD' AND vertical = 'general';
    """)

    # Clean gov_related_entity description in 990
    op.execute("""
        UPDATE document_schemas
        SET schema_fields = (
            SELECT jsonb_agg(
                CASE
                    WHEN elem->>'name' = 'gov_related_entity'
                    THEN jsonb_set(elem, '{description}', '"IRS990/RelatedEntityInd — whether the organization has disclosed related entities."')
                    ELSE elem
                END
            )
            FROM jsonb_array_elements(schema_fields) AS elem
        )
        WHERE document_type = '990' AND vertical = 'general';
    """)

    # Clean law_firm_filer description in SOS-FILING
    op.execute("""
        UPDATE document_schemas
        SET schema_fields = (
            SELECT jsonb_agg(
                CASE
                    WHEN elem->>'name' = 'law_firm_filer'
                    THEN jsonb_set(elem, '{description}', '"Name of law firm or attorney that submitted the filing."')
                    ELSE elem
                END
            )
            FROM jsonb_array_elements(schema_fields) AS elem
        )
        WHERE document_type = 'SOS-FILING' AND vertical = 'general';
    """)

    # Clean contractor_name description in BUILDING-PERMIT
    op.execute("""
        UPDATE document_schemas
        SET schema_fields = (
            SELECT jsonb_agg(
                CASE
                    WHEN elem->>'name' = 'contractor_name'
                    THEN jsonb_set(elem, '{description}', '"Contractor or builder name — second part of the OWNER OR BUILDER field after the slash."')
                    ELSE elem
                END
            )
            FROM jsonb_array_elements(schema_fields) AS elem
        )
        WHERE document_type = 'BUILDING-PERMIT' AND vertical = 'general';
    """)

    # Clean estimated_value description in BUILDING-PERMIT
    op.execute("""
        UPDATE document_schemas
        SET schema_fields = (
            SELECT jsonb_agg(
                CASE
                    WHEN elem->>'name' = 'estimated_value'
                    THEN jsonb_set(elem, '{description}', '"Estimated construction value in dollars."')
                    ELSE elem
                END
            )
            FROM jsonb_array_elements(schema_fields) AS elem
        )
        WHERE document_type = 'BUILDING-PERMIT' AND vertical = 'general';
    """)


def downgrade() -> None:
    op.execute("""
        UPDATE document_schemas
        SET vertical = 'general'
        WHERE document_type = 'OBITUARY';
    """)
    # Note: extraction_prompt and field description restores are not implemented.
    # Re-seed from the original seed file state via git history if needed.
