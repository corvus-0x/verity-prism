"""schema_cleanup_obituary_and_sr_references

Revision ID: c8dd75f9d15c
Revises: d4e9f2a83b17
Create Date: 2026-05-27 02:27:53.540527

Moves OBITUARY to the fraud vertical (it is a fraud investigation tool, not a
general IDP feature) and removes SR signal code references from general schema
extraction_prompts and field descriptions (those codes belong in the fraud
vertical cap, not general schema definitions).

downgrade() restores the affected general schemas to their CANONICAL pre-cleanup
seed values (recovered from git revision 6f655fa^). This is deterministic
restoration to the known reference-data state — NOT a guarantee of per-database
"exact prior state": a database that manually edited document_schemas after this
migration ran cannot be reconstructed without a snapshot, which does not exist on
already-migrated DBs. upgrade() is intentionally left unchanged (editing the
upgrade of a shipped migration would not re-run on DBs already past it).
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c8dd75f9d15c"
down_revision: str | None = "d4e9f2a83b17"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# ── Canonical pre-cleanup values (recovered from git 6f655fa^) ──────────────────
# Restored by downgrade(). Keyed to EXACTLY the surfaces upgrade() changed.

# (document_type, field_name) -> original field description
_ORIGINAL_DESCRIPTIONS = {
    (
        "PARCEL-RECORD",
        "owner_occupied",
    ): "Whether the property is owner-occupied. N on a nonprofit-owned residential property is a signal.",
    (
        "990",
        "gov_related_entity",
    ): "IRS990/RelatedEntityInd — does org have related entities? False when known related entities exist = SR-025 signal",
    (
        "SOS-FILING",
        "law_firm_filer",
    ): "Name of law firm or attorney that submitted the filing — repeated appearance of same firm across entities is a network signal",
    (
        "BUILDING-PERMIT",
        "contractor_name",
    ): "Contractor or builder name — second part of the OWNER OR BUILDER field after the slash. Repeated appearance of the same contractor across an entity's permits is a network signal.",
    (
        "BUILDING-PERMIT",
        "estimated_value",
    ): "Estimated construction value in dollars. Compare to organization's annual revenue to detect SR-026 CONSTRUCTION_OVERAGE signal.",
}

# document_type -> full original extraction_prompt
_ORIGINAL_PROMPTS = {
    "990": """Extract structured data from this IRS Form 990 XML filing.

This is structured XML data — not a scanned document. Every value is in a clearly labeled XML element.
Read element names and their text content directly. Do not guess or infer values.

CRITICAL RULES:

XML structure:
- The document is wrapped in <Return xmlns="http://www.irs.gov/efile">
- Filing metadata is in <ReturnHeader>
- Financial and governance data is in <ReturnData><IRS990>
- Schedules are in <ReturnData><IRS990ScheduleA>, <IRS990ScheduleD>, etc.

Amounts:
- All dollar amounts are integers (no decimal points) in the XML
- A value of 2250487 means $2,250,487
- Extract the raw integer value, not formatted

Booleans:
- XML values are "true" or "false" (lowercase)
- Convert to true/false for boolean fields
- "X" in a field typically means "checked/yes" — treat as true

Officers (Part VII Section A):
- There are multiple <Form990PartVIISectionAGrp> elements
- Extract each one as officer_1, officer_2, etc. in document order
- $0 compensation for all officers at an org with millions in revenue is a signal

Program service revenue (Part VIII):
- There are multiple <ProgramServiceRevenueGrp> elements
- Extract each as program_revenue_1, program_revenue_2, etc.
- The UnrelatedBusinessRevenueAmt is the portion that triggers 990T filing

Related entities:
- RelatedEntityInd = false when known related entities exist = FALSE DISCLOSURE signal (SR-025)
- Schedule R lists related organizations — extract all entries
- Empty Schedule R combined with false RelatedEntityInd is a critical flag

Schedule O:
- Contains supplemental explanations for form lines
- Extract all <SupplementalInformationDetail> entries
- These often contain the most candid disclosures

Missing schedules:
- If a schedule element does not appear in the XML, leave those fields null
- Do not fabricate values for absent schedules

990T filings:
- Form 990T is the Unrelated Business Income Tax return
- It has a different structure from Form 990
- For 990T files, extract only header fields (tax_year, ein, org_name, return_type, etc.)
- Financial fields specific to Form 990 will be null for 990T filings""",
    "UCC": """Extract structured data from this UCC (Uniform Commercial Code) financing statement or amendment filed with a state Secretary of State.

UCC FILING TYPES:

UCC1 — Original Financing Statement: Creates a new security interest.
  - Has its own FS number (e.g. OH00220042448)
  - Lists debtors, secured parties, and collateral
  - Check the filing type checkboxes: Agriculture Lien, Public Finance, Manufactured Home
  - The lapse date is 5 years from filing unless the financing statement says otherwise

UCC3 — Amendment: Modifies an existing financing statement.
  - References the original FS number it is amending
  - Amendment types: Continuation (extends lapse), Termination (releases lien), Debtor Add/Delete (changes who is bound), Collateral Change, Assignment
  - Most amendments do NOT restate the full collateral — they only show what changed

CRITICAL FIELDS:

filing_time: Extract the EXACT time (HH:MM:SS) from the timestamp — not just the date.
  Multiple amendments filed within seconds or minutes of each other indicate a coordinated batch
  submission (the UCC_BURST signal SR-004). The time gap between sequential filings is investigatively
  significant. Format: HH:MM:SS as it appears in the document.

original_fs_number: For amendments, this is the FS number of the underlying financing statement
  being modified — NOT the SR/document number of this amendment itself. Always extract the original FS
  number separately from the document's own filing number.

packet_number: The internal number assigned by the filing agent (Diligenz, CSC). Sequential packet
  numbers on multiple amendments confirm they were submitted as a batch rather than independently.

Debtors and secured parties:
  - Extract ALL named debtors — agricultural filings frequently list multiple family members
  - Record each person's name exactly as it appears, including middle initials
  - Note whether each debtor is an individual or an organization
  - For amendments that ADD a debtor: extract the new debtor under the debtor fields
  - For amendments that DELETE a debtor: note this in the amendment_type field

Collateral:
  - For UCC1 originals: extract the COMPLETE verbatim collateral description
  - For UCC3 amendments: note that collateral is in the original if not shown here
  - Agricultural collateral (livestock, crops, equipment) vs. blanket all-assets lien are very different

Filer information:
  - The filer may be the secured party itself (bank employee filing directly) or a commercial filing
    service (Diligenz, CSC) acting as an agent
  - Employee names in email addresses (e.g. brenda.mescher@e-farmcredit.com) identify individuals
    at the creditor — extract the email even if it reveals a name

If a field is not present in this document type (e.g. collateral on a continuation amendment), leave it null.""",
    "BUILDING-PERMIT": """Extract structured data from this building permit record.

Building permit records come in two formats:

SPREADSHEET FORMAT (Excel): Each row is one permit with columns:
  DATE | PERMIT # | OWNER OR BUILDER | ADDRESS | CITY / TWP | TYPE | EST. VALUE | SQ. FT. | USE GROUP

  For the OWNER OR BUILDER field: split on the "/" character.
  - Everything before "/" is the owner_name
  - Everything after "/" is the contractor_name
  - If there is no "/" the entire field is the owner_name

PDF FORMAT (individual permit): A single-page official permit document with labeled fields.
  Extract all labeled fields present on the form.

FIELD NOTES:

permit_type: If this came from a commercial permit spreadsheet, set to "Commercial".
  If from a residential spreadsheet, set to "Residential".

estimated_value: Extract as a plain integer (no $ sign or commas).
  This value is used to compute the SR-026 CONSTRUCTION_OVERAGE signal:
  if estimated_value > total organization revenue for the same year, the signal fires.

work_description: Copy the complete TYPE field verbatim — do not summarize.
  "NEW RESTAURANT & COMM. OUTREACH FACILITY" is more investigatively useful
  than "new construction."

contractor_name: The construction company is often the investigative link.
  If the same contractor appears on multiple permits for the same owner,
  extract it consistently so the relationship is queryable.

use_group: IBC codes — A=Assembly, B=Business, E=Educational, F=Factory/Industrial,
  I=Institutional, M=Mercantile, R=Residential, S=Storage, U=Utility/Misc.
  R-1 and R-2 are specific residential subtypes. For residential permit spreadsheets,
  this column contains a sequential count number rather than an IBC code.

If a field is not present, leave it null.""",
}


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
    """Restore the affected general schemas to their canonical pre-cleanup seed values.

    Deterministic restoration to known reference-data values (see module docstring) —
    not a per-database exact-snapshot restore. Each UPDATE is scoped to its
    document_type and no-ops safely on a DB that lacks the row.
    """
    bind = op.get_bind()

    # 1. OBITUARY back to the general vertical
    op.execute("""
        UPDATE document_schemas
        SET vertical = 'general'
        WHERE document_type = 'OBITUARY';
    """)

    # 2. Restore full original extraction_prompts (canonical pre-cleanup text)
    for dtype, prompt in _ORIGINAL_PROMPTS.items():
        bind.execute(
            sa.text(
                "UPDATE document_schemas SET extraction_prompt = :p "
                "WHERE document_type = :t AND vertical = 'general'"
            ).bindparams(p=prompt, t=dtype)
        )

    # 3. Restore original field descriptions (jsonb_set, scoped per document_type)
    for (dtype, field), desc in _ORIGINAL_DESCRIPTIONS.items():
        bind.execute(
            sa.text(
                "UPDATE document_schemas "
                "SET schema_fields = ("
                "  SELECT jsonb_agg("
                "    CASE WHEN elem->>'name' = :f "
                "         THEN jsonb_set(elem, '{description}', to_jsonb(CAST(:d AS text))) "
                "         ELSE elem END"
                "  ) FROM jsonb_array_elements(schema_fields) AS elem"
                ") "
                "WHERE document_type = :t AND vertical = 'general'"
            ).bindparams(f=field, d=desc, t=dtype)
        )
