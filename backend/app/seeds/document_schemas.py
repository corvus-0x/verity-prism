"""
Seed the document_schemas table with extraction schemas derived from real investigation documents.
Run inside Docker: docker-compose exec backend python -m app.seeds.document_schemas
"""
import sys
from app.database import SessionLocal
from app.models.document_schema import DocumentSchema


def _fields(*sections):
    """Flatten section lists into one list."""
    result = []
    for section in sections:
        result.extend(section)
    return result


def _repeating(prefix, count, fields):
    """Generate numbered repeating field sets, e.g. sale_1_date through sale_8_date."""
    result = []
    for i in range(1, count + 1):
        for name, ftype, desc in fields:
            result.append({
                "name": f"{prefix}_{i}_{name}",
                "type": ftype,
                "description": f"[Record {i}] {desc}",
                "required": False,
            })
    return result


# ── Field sections ────────────────────────────────────────────────────────────

IDENTITY = [
    {"name": "parcel_number",       "type": "id_number", "description": "Official county parcel identifier at the top of the document", "required": True},
    {"name": "owner_name",          "type": "name",      "description": "Current owner of record as shown in the Location section", "required": True},
    {"name": "property_address",    "type": "address",   "description": "Physical property address", "required": True},
    {"name": "county",              "type": "text",      "description": "County name (e.g. Darke County, Mercer County)", "required": True},
    {"name": "township",            "type": "text",      "description": "Township (e.g. PATTERSON TWP)", "required": False},
    {"name": "municipality",        "type": "text",      "description": "Municipality (e.g. OSGOOD CORP, UNINCORPORATED)", "required": False},
    {"name": "school_district",     "type": "text",      "description": "School district name", "required": False},
    {"name": "deeded_owner_name",   "type": "name",      "description": "Owner name from the Deeded Owner Address section", "required": False},
    {"name": "deeded_owner_address","type": "address",   "description": "Mailing address from the Deeded Owner section — may differ from taxpayer address", "required": False},
    {"name": "taxpayer_name",       "type": "name",      "description": "Owner name from the Tax Payer Address section", "required": False},
    {"name": "taxpayer_address",    "type": "address",   "description": "Mailing address from the Tax Payer section — flag if different from deeded owner address", "required": False},
    {"name": "owner_is_trust",      "type": "boolean",   "description": "True if owner name contains TRUSTEE, TRUST, or similar trust language", "required": False},
    {"name": "trust_name",          "type": "text",      "description": "Full name of the trust if owner_is_trust is true", "required": False},
    {"name": "trustee_name",        "type": "name",      "description": "Name of the trustee if owner_is_trust is true", "required": False},
    {"name": "owner_entity_type",   "type": "text",      "description": "individual, LLC, nonprofit, trust, or government", "required": False},
]

LEGAL = [
    {"name": "legal_description",        "type": "text",      "description": "Primary legal description from the Legal section", "required": False},
    {"name": "legal_description_line_2", "type": "text",      "description": "Second line of legal description (Mercer County format)", "required": False},
    {"name": "legal_description_line_3", "type": "text",      "description": "Third line of legal description (Mercer County format)", "required": False},
    {"name": "rts_notation",             "type": "text",      "description": "Range-Township-Section notation (e.g. 003-07-26, Mercer County format)", "required": False},
    {"name": "legal_acres",              "type": "text",      "description": "Legal acreage from the Legal section", "required": False},
    {"name": "land_use_code",            "type": "text",      "description": "Numeric land use classification code (e.g. 430, 500, 510, 640, 680)", "required": False},
    {"name": "land_use_description",     "type": "text",      "description": "Human-readable land use description (e.g. Restaurant, Single Family Dwelling, Charitable Exempts)", "required": False},
    {"name": "map_number",               "type": "text",      "description": "Map reference number if present", "required": False},
    {"name": "neighborhood_code",        "type": "text",      "description": "Assessor neighborhood code (e.g. 00940, 003169)", "required": False},
    {"name": "subdivision_name",         "type": "text",      "description": "Subdivision name from legal description (e.g. DO GOOD SUB DIV, MARION ACRES, BREWERS SOUTH ADDN)", "required": False},
    {"name": "card_count",               "type": "text",      "description": "Number of appraisal cards. 0 means no structure on the parcel.", "required": False},
    {"name": "lender_id",                "type": "id_number", "description": "Lender ID from Legal section. 0 means no lender. Non-zero values identify a financing institution.", "required": False},
    {"name": "tax_lien",                 "type": "boolean",   "description": "Whether a tax lien exists on the property (Y/N or True/False)", "required": False},
    {"name": "foreclosure",              "type": "boolean",   "description": "Whether the property is in foreclosure", "required": False},
    {"name": "homestead_reduction",      "type": "boolean",   "description": "Whether a homestead reduction applies", "required": False},
    {"name": "owner_occupied",           "type": "boolean",   "description": "Whether the property is owner-occupied. N on a nonprofit-owned residential property is a signal.", "required": False},
    {"name": "board_of_revision",        "type": "boolean",   "description": "Whether a valuation challenge is pending before the Board of Revision", "required": False},
    {"name": "new_construction",         "type": "boolean",   "description": "Whether flagged as new construction", "required": False},
    {"name": "divided_property",         "type": "boolean",   "description": "Whether the property has been divided", "required": False},
    {"name": "parcel_created_by_plat",   "type": "boolean",   "description": "True if the most recent sale deed type is PT-PLAT, meaning this parcel was created by subdivision platting", "required": False},
    {"name": "on_cauv",                  "type": "boolean",   "description": "Whether enrolled in Current Agricultural Use Valuation program", "required": False},
    {"name": "has_sketch",               "type": "boolean",   "description": "False if the document header says No Sketches for this Parcel", "required": False},
    {"name": "special_notice",           "type": "text",      "description": "Content of the Special Notice section if present (Mercer County format)", "required": False},
]

UTILITIES = [
    {"name": "utilities_electric", "type": "text",    "description": "Electric utility availability (Available/Unknown)", "required": False},
    {"name": "utilities_gas",      "type": "text",    "description": "Gas utility availability", "required": False},
    {"name": "utilities_water",    "type": "text",    "description": "Water utility availability", "required": False},
    {"name": "utilities_sewer",    "type": "text",    "description": "Sewer utility availability", "required": False},
    {"name": "sidewalks",          "type": "boolean", "description": "Whether sidewalks are present", "required": False},
    {"name": "curbs",              "type": "boolean", "description": "Whether curbs are present", "required": False},
    {"name": "topography",         "type": "text",    "description": "Topography description (Flat/Rolling/Unknown)", "required": False},
    {"name": "roads_type",         "type": "text",    "description": "Road type adjacent to parcel (Paved/Gravel/Unknown)", "required": False},
]

VALUATION_CURRENT = [
    {"name": "appraised_value_current",  "type": "currency", "description": "Most recent total appraised value (100%)", "required": False},
    {"name": "appraised_land",           "type": "currency", "description": "Land portion of current appraised value", "required": False},
    {"name": "appraised_improvements",   "type": "currency", "description": "Improvements (buildings) portion of current appraised value", "required": False},
    {"name": "assessed_land",            "type": "currency", "description": "Assessed land value (35% of appraised)", "required": False},
    {"name": "assessed_improvements",    "type": "currency", "description": "Assessed improvements value (35% of appraised)", "required": False},
    {"name": "assessed_total",           "type": "currency", "description": "Total assessed value (35% of appraised) — what taxes are computed on", "required": False},
    {"name": "land_appraised_cauv",      "type": "currency", "description": "CAUV value of land when enrolled in agricultural use program — often dramatically lower than market value", "required": False},
    {"name": "improvement_demolished",   "type": "boolean",  "description": "True if current improvements = $0 but any prior year in the history shows improvements > $50,000", "required": False},
]

# Valuation history: 6 years newest to oldest
VALUATION_HISTORY = _repeating("val_year", 6, [
    ("label",          "text",     "Year label (e.g. 2023, 2020)"),
    ("total",          "currency", "Total appraised value for this year"),
    ("improvements",   "currency", "Improvements portion — track this for demolition detection"),
    ("assessed_total", "currency", "Assessed total (35%) for this year"),
])

EXEMPTION = [
    {"name": "tax_exempt",            "type": "boolean",  "description": "True if any charitable/government exemption applies", "required": False},
    {"name": "tax_exempt_category",   "type": "text",     "description": "Exemption category (e.g. 680 - Charitable Exempts, 640 - Municipal)", "required": False},
    {"name": "exemption_market_value","type": "currency", "description": "Market value being shielded from taxation", "required": False},
    {"name": "exemption_assessed_value","type": "currency","description": "Assessed value being shielded from taxation", "required": False},
]

TAX_CURRENT = [
    {"name": "tax_annual_charge",       "type": "currency", "description": "Gross tax charge before any reductions (Year Total column, CHARGE row)", "required": False},
    {"name": "tax_adjustment",          "type": "currency", "description": "Tax adjustment amount", "required": False},
    {"name": "tax_reduction_amount",    "type": "currency", "description": "Reduction applied to gross charge", "required": False},
    {"name": "tax_non_business_credit", "type": "currency", "description": "Non-business credit amount", "required": False},
    {"name": "owner_occupancy_credit",  "type": "currency", "description": "Owner occupancy credit — should be $0 for nonprofit or non-owner-occupied properties", "required": False},
    {"name": "homestead_credit_amount", "type": "currency", "description": "Homestead credit — should be $0 for nonprofit owners", "required": False},
    {"name": "tax_local_homestead",     "type": "currency", "description": "Local homestead credit amount", "required": False},
    {"name": "tax_sales_credit",        "type": "currency", "description": "Sales credit amount", "required": False},
    {"name": "tax_annual_net",          "type": "currency", "description": "Net annual tax after all reductions (NET TAX row, Year Total)", "required": False},
    {"name": "tax_cauv_recoupment",     "type": "currency", "description": "CAUV recoupment charge — applies when land leaves agricultural status", "required": False},
    {"name": "tax_special_assessments", "type": "currency", "description": "Total special assessments (Year Total)", "required": False},
    {"name": "tax_penalty_interest",    "type": "currency", "description": "Penalty and interest — non-zero signals delinquency", "required": False},
    {"name": "tax_net_owed",            "type": "currency", "description": "Total net owed (NET OWED row, Year Total)", "required": False},
    {"name": "tax_net_paid",            "type": "currency", "description": "Total net paid (NET PAID row, Year Total)", "required": False},
    {"name": "tax_net_due",             "type": "currency", "description": "Outstanding balance currently due (NET DUE row, Year Total)", "required": False},
    {"name": "tax_delinquency_amount",  "type": "currency", "description": "Past due delinquency amount (Delinquency column)", "required": False},
    {"name": "tax_escrow",              "type": "currency", "description": "Escrow amount", "required": False},
    {"name": "tax_surplus",             "type": "currency", "description": "Surplus amount", "required": False},
    {"name": "tax_rate_nominal",        "type": "text",     "description": "Nominal tax rate (e.g. 44.850000)", "required": False},
    {"name": "tax_rate_effective",      "type": "text",     "description": "Effective tax rate after credits (e.g. 40.186887)", "required": False},
]

TAX_DISTRIBUTIONS = [
    {"name": "tax_dist_school_pct",      "type": "text",     "description": "Percentage of tax going to school district", "required": False},
    {"name": "tax_dist_school_amount",   "type": "currency", "description": "Dollar amount going to school district", "required": False},
    {"name": "tax_dist_township_pct",    "type": "text",     "description": "Percentage going to township", "required": False},
    {"name": "tax_dist_township_amount", "type": "currency", "description": "Dollar amount going to township", "required": False},
    {"name": "tax_dist_county_pct",      "type": "text",     "description": "Percentage going to county", "required": False},
    {"name": "tax_dist_county_amount",   "type": "currency", "description": "Dollar amount going to county", "required": False},
    {"name": "tax_dist_city_pct",        "type": "text",     "description": "Percentage going to city/village — $0 on unincorporated parcels", "required": False},
    {"name": "tax_dist_city_amount",     "type": "currency", "description": "Dollar amount going to city/village", "required": False},
]

# Tax payment history: 8 payments newest to oldest
TAX_PAYMENTS = _repeating("tax_payment", 8, [
    ("date",        "date",     "Payment date"),
    ("cycle",       "text",     "Payment cycle code (e.g. 1-25, 2-24)"),
    ("first_half",  "currency", "First half payment amount"),
    ("second_half", "currency", "Second half payment amount"),
    ("receipt",     "text",     "Receipt number"),
])

# Special assessments: up to 3
SPECIAL_ASSESSMENTS = _repeating("special_assessment", 3, [
    ("name",        "text",     "Project name (e.g. 12-305 81-91 MILE LORAMIE CREEK)"),
    ("first_half",  "currency", "First half assessment amount"),
    ("second_half", "currency", "Second half assessment amount"),
    ("total",       "currency", "Total annual special assessment"),
])

# Sales history: 8 sales newest to oldest
SALES = _repeating("sale", 8, [
    ("date",                "date",      "Sale date — treat 11/11/1900 as null (system placeholder)"),
    ("buyer",               "name",      "Buyer name"),
    ("seller",              "name",      "Seller name — blank for PT-PLAT entries"),
    ("amount",              "currency",  "Sale amount"),
    ("deed_type",           "text",      "Deed type code: WD=Warranty Deed, EX=Exempt Transfer, PT-PLAT=Plat Creation, FD=Fiduciary Deed, ED=Executive Deed"),
    ("conveyance_number",   "id_number", "Conveyance number — EX suffix means exempt transfer"),
    ("book_page",           "id_number", "Deed book and page reference"),
    ("valid",               "boolean",   "Whether the county considers this a valid arm's-length market sale"),
    ("parcels_in_sale",     "text",      "Number of parcels included in this single conveyance — >1 means a bundle sale"),
    ("seller_is_individual","boolean",   "True if seller appears to be a private person rather than an LLC, Inc, Trust, or government entity"),
    ("appraised_at_sale",   "currency",  "Appraised value in the year of the sale — find in valuation history table"),
])

DWELLING = [
    {"name": "dwelling_year_built",              "type": "text", "description": "Year the primary dwelling was built", "required": False},
    {"name": "dwelling_year_remodeled",          "type": "text", "description": "Year of most recent remodel", "required": False},
    {"name": "dwelling_style",                   "type": "text", "description": "Dwelling style (Ranch, Conventional, Colonial, etc.)", "required": False},
    {"name": "dwelling_stories",                 "type": "text", "description": "Number of stories", "required": False},
    {"name": "dwelling_exterior_wall",           "type": "text", "description": "Exterior wall material code (WD/ALM, FRwMAS, etc.)", "required": False},
    {"name": "dwelling_heating_type",            "type": "text", "description": "Heating type", "required": False},
    {"name": "dwelling_cooling_type",            "type": "text", "description": "Cooling type", "required": False},
    {"name": "dwelling_basement_type",           "type": "text", "description": "Basement type (Full, Pt Bsmt/Pt Crawl, None, etc.)", "required": False},
    {"name": "dwelling_attic",                   "type": "text", "description": "Attic type (Full Finished, None, etc.)", "required": False},
    {"name": "dwelling_finished_sqft",           "type": "text", "description": "Total finished living area in square feet", "required": False},
    {"name": "dwelling_first_floor_area",        "type": "text", "description": "First floor area in square feet", "required": False},
    {"name": "dwelling_upper_floor_area",        "type": "text", "description": "Upper floor area in square feet", "required": False},
    {"name": "dwelling_total_basement_area",     "type": "text", "description": "Total basement area in square feet", "required": False},
    {"name": "dwelling_finished_basement_area",  "type": "text", "description": "Finished basement area in square feet", "required": False},
    {"name": "dwelling_number_of_rooms",         "type": "text", "description": "Total number of rooms", "required": False},
    {"name": "dwelling_bedrooms",                "type": "text", "description": "Number of bedrooms", "required": False},
    {"name": "dwelling_full_baths",              "type": "text", "description": "Number of full bathrooms", "required": False},
    {"name": "dwelling_half_baths",              "type": "text", "description": "Number of half bathrooms", "required": False},
    {"name": "dwelling_grade",                   "type": "text", "description": "County quality grade (A through D)", "required": False},
    {"name": "dwelling_grade_adjustment",        "type": "text", "description": "Grade adjustment multiplier (e.g. 0.80, 1.00)", "required": False},
    {"name": "dwelling_condition",               "type": "text", "description": "Condition code (AV=Average, VG=Very Good, G=Good, P=Poor)", "required": False},
    {"name": "dwelling_fireplace_openings",      "type": "text", "description": "Number of fireplace openings", "required": False},
]

COMMERCIAL = [
    {"name": "commercial_occupancy_code",        "type": "text", "description": "Commercial occupancy type code (e.g. 322=Fire Station, 323=Fraternal Building, 350=Restaurant)", "required": False},
    {"name": "commercial_occupancy_description", "type": "text", "description": "Commercial occupancy description", "required": False},
    {"name": "commercial_year_built",            "type": "text", "description": "Year commercial structure was built", "required": False},
    {"name": "commercial_effective_age",         "type": "text", "description": "Effective age for assessment purposes", "required": False},
    {"name": "commercial_class",                 "type": "text", "description": "Commercial construction class (A through D)", "required": False},
    {"name": "commercial_section_area",          "type": "text", "description": "Total commercial section area in square feet", "required": False},
    {"name": "commercial_wall_height",           "type": "text", "description": "Wall height in feet", "required": False},
    {"name": "commercial_section_stories",       "type": "text", "description": "Number of stories", "required": False},
]

# Improvements (non-building structures): up to 5
IMPROVEMENTS = _repeating("improvement", 5, [
    ("description", "text",     "Description (e.g. Garage Fr, BT Paving, Mtl/Fr Pole Barn)"),
    ("year_built",  "text",     "Year built — 1900/1901 values are placeholders meaning unknown"),
    ("area_sqft",   "text",     "Area in square feet"),
    ("condition",   "text",     "Condition code (AV AV, VG VG, P P)"),
    ("value",       "currency", "Appraised value at 100%"),
])

# Additions: up to 5
ADDITIONS = _repeating("addition", 5, [
    ("code",        "text",     "Addition type code (GR1=Frame Garage, PR1=Open Porch, PR2=Enclosed Porch, PT2=Patio)"),
    ("description", "text",     "Addition description"),
    ("base_area",   "text",     "Base area in square feet"),
    ("year_built",  "text",     "Year built"),
])

# Land segments: up to 3
LAND_SEGMENTS = _repeating("land_segment", 3, [
    ("type",         "text",     "Land type code and description (e.g. L1 - Front Lot Entry, A3 - Residual)"),
    ("acres",        "text",     "Acres for this segment"),
    ("frontage",     "text",     "Actual frontage in feet"),
    ("depth_factor", "text",     "Depth factor percentage — >100% means a premium applies"),
    ("market_value", "currency", "Market value for this segment"),
])


EXTRACTION_PROMPT = """Extract structured data from this county auditor parcel record. These records come from Ohio county auditor websites and describe a single property parcel.

CRITICAL RULES:

Date handling:
- The date 11/11/1900 is a system placeholder meaning no recorded date — extract as null
- Extract real dates in the format they appear (e.g. 9/15/2017)

Sales history:
- Extract sales in order from most recent to oldest, up to 8 entries
- PT-PLAT deed type means this parcel was created by subdivision platting — there is no seller, set seller to null
- EX or 637EX or any conveyance number ending in EX means Exempt Transfer between organizations
- FD = Fiduciary Deed (trust administration), ED = Executive Deed (probate/estate)
- valid field: extract the YES/NO/UNKNOWN value from the Valid column
- parcels_in_sale: the count in the Parcels In Sale column — >1 means a bundle transaction
- seller_is_individual: true if seller name is a person (not LLC, INC, CORP, TRUST, or government)
- appraised_at_sale: find the appraised total in the valuation history table for the year matching the sale date

Valuation history:
- Extract rows newest to oldest, up to 6 years
- Each row has: year label, total appraised, improvements value, assessed total
- improvement_demolished: set to true if current improvements = $0 AND any prior year shows improvements > $50,000

Ownership:
- owner_is_trust: true if owner name contains TRUSTEE, TRUST, or IRREVOCABLE TRUST
- owner_entity_type: individual, LLC, nonprofit, trust, or government
- If deeded_owner_address differs from taxpayer_address — extract both carefully, this discrepancy is investigatively significant

Tax fields:
- Extract from the Tax section table using the Year Total column
- homestead_credit_amount and owner_occupancy_credit: flag if non-zero on a nonprofit-owned property
- tax_net_due: the outstanding balance from the NET DUE row, Year Total column

Booleans:
- Convert Y/N to true/false
- Convert True/False text to true/false
- Convert present/absent fields to true/false as appropriate

Mercer County format differences:
- Parcel number is purely numeric (no M51 prefix)
- Legal section has separate utility fields (Electric, Gas, Water, Sewer) — extract these
- Has a Deeds section separate from Sales section
- Has a Special Notice section at the top
- RTS notation (e.g. 003-07-26) appears in the Legal section

If a section is absent or says No Records Found — leave all fields in that section as null."""


def seed_parcel_record_schema(db):
    """Insert the PARCEL-RECORD schema if it doesn't already exist."""
    existing = db.query(DocumentSchema).filter(
        DocumentSchema.document_type == "PARCEL-RECORD"
    ).first()

    if existing:
        print("PARCEL-RECORD schema already exists — skipping.")
        return existing

    schema_fields = _fields(
        IDENTITY,
        LEGAL,
        UTILITIES,
        VALUATION_CURRENT,
        VALUATION_HISTORY,
        EXEMPTION,
        TAX_CURRENT,
        TAX_DISTRIBUTIONS,
        TAX_PAYMENTS,
        SPECIAL_ASSESSMENTS,
        SALES,
        DWELLING,
        COMMERCIAL,
        IMPROVEMENTS,
        ADDITIONS,
        LAND_SEGMENTS,
    )

    schema = DocumentSchema(
        document_type="PARCEL-RECORD",
        display_name="County Auditor Parcel Record",
        vertical="fraud",
        schema_fields=schema_fields,
        extraction_prompt=EXTRACTION_PROMPT,
        version=1,
        is_active=True,
    )
    db.add(schema)
    db.commit()
    db.refresh(schema)
    print(f"PARCEL-RECORD schema created — {len(schema_fields)} fields.")
    return schema


# ── DEED schema ───────────────────────────────────────────────────────────────

DEED_RECORDING = [
    {"name": "instrument_number",   "type": "id_number", "description": "Official instrument/recording number assigned by the county recorder", "required": True},
    {"name": "book",                "type": "id_number", "description": "Official Records book or volume number", "required": False},
    {"name": "page",                "type": "id_number", "description": "Page number within the book", "required": False},
    {"name": "pages",               "type": "text",      "description": "Total number of pages in the instrument", "required": False},
    {"name": "recording_date",      "type": "date",      "description": "Date the instrument was recorded with the county recorder", "required": True},
    {"name": "recording_time",      "type": "text",      "description": "Time of recording (e.g. 10:46 AM)", "required": False},
    {"name": "recording_fee",       "type": "currency",  "description": "Fee paid to the recorder to file this instrument", "required": False},
    {"name": "recorder_name",       "type": "name",      "description": "Name of the county recorder who accepted the filing", "required": False},
    {"name": "recording_county",    "type": "text",      "description": "County where the deed was recorded", "required": True},
    {"name": "recording_state",     "type": "text",      "description": "State where the deed was recorded", "required": False},
]

DEED_AUDITOR = [
    {"name": "auditor_name",                  "type": "name",      "description": "County auditor name from the transfer stamp", "required": False},
    {"name": "auditor_signatory",             "type": "name",      "description": "Deputy who signed the auditor stamp line (e.g. Paula Schrader)", "required": False},
    {"name": "auditor_review_date",           "type": "date",      "description": "Date the auditor reviewed and stamped the deed", "required": False},
    {"name": "engineer_review_date",          "type": "date",      "description": "Date the county engineer reviewed the deed", "required": False},
    {"name": "engineer_signatory",            "type": "text",      "description": "Initials or name on the county engineer review stamp", "required": False},
    {"name": "conveyance_fee_amount",         "type": "currency",  "description": "Conveyance fee paid to the county auditor. Use this to compute implied sale price.", "required": False},
    {"name": "conveyance_fee_exempt",         "type": "boolean",   "description": "True if the conveyance fee was waived/exempt (stamp shows Exempt)", "required": False},
    {"name": "conveyance_fee_exemption_code", "type": "text",      "description": "Specific ORC exemption code applied (e.g. EL). Identifies the legal basis for the exemption.", "required": False},
    {"name": "implied_sale_price",            "type": "currency",  "description": "Computed sale price based on conveyance fee. Darke County rate: $0.005 per dollar ($5/$1,000). Mercer County may differ.", "required": False},
]

DEED_TYPE = [
    {"name": "deed_type",     "type": "text", "description": "Type of deed instrument: WARRANTY DEED, QUITCLAIM DEED, FIDUCIARY DEED, EXECUTOR DEED, CORRECTION DEED, etc.", "required": True},
    {"name": "warranty_type", "type": "text", "description": "Level of title warranty: general warranty, limited warranty, fiduciary covenants, or none (quitclaim)", "required": False},
]

DEED_DATES = [
    {"name": "execution_date",      "type": "date", "description": "Date the grantor signed the deed", "required": False},
    {"name": "acknowledgment_date", "type": "date", "description": "Date the notary took the acknowledgment — may differ from execution date", "required": False},
]

DEED_GRANTOR = [
    {"name": "grantor_name",              "type": "name", "description": "Full legal name of the grantor (seller/transferor)", "required": True},
    {"name": "grantor_entity_type",       "type": "text", "description": "Type of grantor entity: individual, LLC, nonprofit corporation, trust, revocable living trust, etc.", "required": False},
    {"name": "grantor_state",             "type": "text", "description": "State where the grantor entity is organized", "required": False},
    {"name": "grantor_signatory",         "type": "name", "description": "Name of the person who physically signed on behalf of the grantor", "required": False},
    {"name": "grantor_signatory_capacity","type": "text", "description": "Capacity in which the signatory signed: managing member, president, trustee, manager, etc.", "required": False},
    {"name": "grantor_entity_correction", "type": "boolean", "description": "True if this deed corrects an entity type error in a prior recorded instrument", "required": False},
]

DEED_GRANTEE = [
    {"name": "grantee_name",         "type": "name",    "description": "Full legal name of the grantee (buyer/recipient)", "required": True},
    {"name": "grantee_entity_type",  "type": "text",    "description": "Type of grantee entity: individual, LLC, nonprofit corporation, trust, etc.", "required": False},
    {"name": "grantee_state",        "type": "text",    "description": "State where the grantee entity is organized", "required": False},
    {"name": "grantee_mailing_address","type": "address","description": "Tax mailing address for the grantee as stated in the deed body", "required": False},
    {"name": "grantee_vesting_type", "type": "text",    "description": "How grantee(s) take title: joint tenancy, tenants in common, survivorship, etc.", "required": False},
]

DEED_CONSIDERATION = [
    {"name": "consideration_stated",  "type": "boolean", "description": "True if a dollar amount is explicitly stated in the deed body. Usually false — Ohio practice is to use 'valuable consideration paid' without stating the price.", "required": False},
    {"name": "consideration_amount",  "type": "currency","description": "Dollar amount if explicitly stated in the body. Usually null — use implied_sale_price from conveyance fee instead.", "required": False},
    {"name": "consideration_text",    "type": "text",    "description": "Verbatim consideration language from the deed body (e.g. 'for valuable consideration paid')", "required": False},
]

DEED_PROPERTY = [
    {"name": "property_county",              "type": "text",      "description": "County where the property is located (may differ from recording county for cross-county deeds)", "required": False},
    {"name": "property_municipality",        "type": "text",      "description": "Village, city, or township where the property is located", "required": False},
    {"name": "property_address",             "type": "address",   "description": "Street address of the property if stated in the deed", "required": False},
    {"name": "legal_description",            "type": "text",      "description": "Full verbatim legal description of the property being conveyed", "required": True},
    {"name": "subdivision_name",             "type": "text",      "description": "Subdivision or addition name from the legal description (e.g. Do Good Subdivision, Brewer Addition, Marion Acres)", "required": False},
    {"name": "engineer_parcel_id",           "type": "id_number", "description": "County engineer parcel ID from the deed — may use different format than auditor parcel number", "required": False},
    {"name": "prior_deed_volume",            "type": "id_number", "description": "Volume/book of the prior deed in the chain of title", "required": False},
    {"name": "prior_deed_page",              "type": "id_number", "description": "Page of the prior deed in the chain of title", "required": False},
    {"name": "prior_deed_instrument_number", "type": "id_number", "description": "Instrument number of the prior deed (Mercer County and other counties that use instrument numbers instead of book/page)", "required": False},
    {"name": "subject_to_clause",            "type": "text",      "description": "Full text of any subject-to or exceptions clause (easements, highways, restrictions, etc.)", "required": False},
]

DEED_SURVEY = [
    {"name": "surveyor_name",          "type": "name", "description": "Registered surveyor who prepared the legal description or survey exhibit", "required": False},
    {"name": "survey_date",            "type": "date", "description": "Date the survey was performed", "required": False},
    {"name": "survey_plat_reference",  "type": "text", "description": "Plat book, volume, page, or instrument number where the survey is recorded", "required": False},
]

DEED_AUTHORIZATION = [
    {"name": "resolution_reference", "type": "text", "description": "Corporate board resolution number authorizing the transfer — blank if not filled in, which may indicate an invalid authorization", "required": False},
    {"name": "resolution_date",      "type": "date", "description": "Date of the board resolution authorizing the transfer", "required": False},
]

DEED_ACKNOWLEDGMENT = [
    {"name": "acknowledgment_state",  "type": "text", "description": "State where the notarial acknowledgment was taken — flag if different from recording county", "required": False},
    {"name": "acknowledgment_county", "type": "text", "description": "County where the notarial acknowledgment was taken", "required": False},
]

DEED_NOTARY = [
    {"name": "notary_name",                  "type": "name",      "description": "Name of the notary public who took the acknowledgment", "required": False},
    {"name": "notary_registration",          "type": "id_number", "description": "Notary registration or attorney registration number", "required": False},
    {"name": "notary_commission_expiration", "type": "date",      "description": "Expiration date of the notary's commission", "required": False},
]

DEED_PREPARER = [
    {"name": "preparer_name",             "type": "name",    "description": "Name of the attorney or person who prepared the instrument", "required": False},
    {"name": "preparer_firm",             "type": "text",    "description": "Law firm or organization of the preparer", "required": False},
    {"name": "preparer_address",          "type": "address", "description": "Address of the preparer", "required": False},
    {"name": "preparer_registration",     "type": "id_number","description": "Attorney registration number of the preparer", "required": False},
    {"name": "title_search_disclaimer",   "type": "boolean", "description": "True if deed contains 'without benefit of a title search' disclaimer — indicates no title review was done", "required": False},
    {"name": "preparer_note",             "type": "text",    "description": "Any other disclaimer or note on the preparer line", "required": False},
    {"name": "deed_delivery_person",      "type": "text",    "description": "Person or service who physically delivered the deed to the recorder (appears on some county records)", "required": False},
]

DEED_EXTRACTION_PROMPT = """Extract structured data from this recorded deed instrument. Deeds are legal instruments that transfer real property title from one party to another.

DEED TYPES AND WHAT THEY MEAN:
- WARRANTY DEED: Grantor guarantees clear title. Strongest form.
- QUITCLAIM DEED: Grantor transfers whatever interest they have, no title guarantee.
- FIDUCIARY DEED: A trustee conveying trust property. Look for trust names and trustee capacities.
- EXECUTOR / ADMINISTRATOR DEED: Estate conveying property after death.
- CORRECTION DEED: Corrects an error in a prior recorded instrument.
- EXEMPT TRANSFER: A $0 transfer between exempt organizations — conveyance fee is exempt.

CRITICAL RULES:

Parties:
- grantor = the seller/transferor (the party GIVING the property)
- grantee = the buyer/recipient (the party RECEIVING the property)
- grantor_signatory = the person who physically signed — for LLCs this is a member or manager, for nonprofits a president or officer, for trusts a trustee
- grantor_signatory_capacity = their title/role when signing
- grantee_vesting_type: look for language like "for their joint lives with remainder to the survivor" (joint tenancy/survivorship) or "as tenants in common"

Consideration and sale price:
- consideration_stated: true ONLY if a dollar amount appears in the deed body — rare in Ohio
- consideration_text: copy the exact language ("for valuable consideration paid", "for $10 and other valuable consideration", etc.)
- implied_sale_price: compute from conveyance_fee_amount. Darke County rate: divide fee by 0.005. Example: $260 fee ÷ 0.005 = $52,000. If conveyance_fee_exempt is true, implied_sale_price = 0.
- conveyance_fee_exemption_code: extract the specific code if shown (e.g. "EL"). This identifies WHY the transfer is exempt.

Recording information:
- instrument_number: the unique number assigned when filed — appears in the top stamp block
- book and page: the Official Records volume and page — may not appear in Mercer County format
- recording_date: the date stamped by the recorder, not the execution date
- recording_county: where the deed was physically filed

Property:
- legal_description: copy the full verbatim description — do not summarize or abbreviate
- engineer_parcel_id: appears as "Engineer's I.D.#" or "Parcel Number" or "Tax ID" — extract exactly as written
- prior_deed_volume / prior_deed_page: the deed that gave the grantor their title — the chain of title reference
- subject_to_clause: copy all subject-to language verbatim

Dates:
- execution_date: when the grantor signed
- acknowledgment_date: when the notary took the acknowledgment — may be the same or different from execution date
- recording_date: when the recorder filed it

Acknowledgment geography:
- acknowledgment_county: where the notary took the acknowledgment — flag mentally if different from recording_county (indicates signatories are based elsewhere)

Corporate deeds:
- resolution_reference: if the deed says "authorized under Resolution [number]" extract the number. If blank, note that it is blank.
- resolution_date: the date of the authorizing board resolution

Preparer:
- title_search_disclaimer: true if the instrument contains "without benefit of a title search" or similar language
- deed_delivery_person: some counties note who dropped off the deed — extract if present

Multi-page deeds:
- Some deeds have exhibit pages (surveys, legal descriptions) attached. Extract all information from all pages.
- survey information appears on exhibit pages — extract surveyor_name, survey_date, survey_plat_reference from exhibits.

If a field is not present in this document, leave it null."""


def seed_deed_schema(db):
    """Insert the DEED schema if it doesn't already exist."""
    existing = db.query(DocumentSchema).filter(
        DocumentSchema.document_type == "DEED"
    ).first()

    if existing:
        print("DEED schema already exists — skipping.")
        return existing

    schema_fields = _fields(
        DEED_RECORDING,
        DEED_AUDITOR,
        DEED_TYPE,
        DEED_DATES,
        DEED_GRANTOR,
        DEED_GRANTEE,
        DEED_CONSIDERATION,
        DEED_PROPERTY,
        DEED_SURVEY,
        DEED_AUTHORIZATION,
        DEED_ACKNOWLEDGMENT,
        DEED_NOTARY,
        DEED_PREPARER,
    )

    schema = DocumentSchema(
        document_type="DEED",
        display_name="Recorded Deed Instrument",
        vertical="fraud",
        schema_fields=schema_fields,
        extraction_prompt=DEED_EXTRACTION_PROMPT,
        version=1,
        is_active=True,
    )
    db.add(schema)
    db.commit()
    db.refresh(schema)
    print(f"DEED schema created — {len(schema_fields)} fields.")
    return schema


# ── IRS Form 990 schema ───────────────────────────────────────────────────────
# Fields map directly to IRS XML element paths.
# The description includes the XML path so the extraction engine
# (or a direct XML parser) knows exactly where to find each value.

F990_HEADER = [
    {"name": "tax_year",              "type": "text",      "description": "ReturnHeader/TaxYr — 4-digit tax year", "required": True},
    {"name": "tax_period_begin",      "type": "date",      "description": "ReturnHeader/TaxPeriodBeginDt", "required": False},
    {"name": "tax_period_end",        "type": "date",      "description": "ReturnHeader/TaxPeriodEndDt", "required": True},
    {"name": "return_type",           "type": "text",      "description": "ReturnHeader/ReturnTypeCd — 990, 990EZ, 990PF, 990T", "required": True},
    {"name": "filed_timestamp",       "type": "date",      "description": "ReturnHeader/ReturnTs — ISO datetime when the return was submitted", "required": False},
    {"name": "ein",                   "type": "id_number", "description": "ReturnHeader/Filer/EIN", "required": True},
    {"name": "org_name",              "type": "name",      "description": "ReturnHeader/Filer/BusinessName/BusinessNameLine1Txt", "required": True},
    {"name": "org_address",           "type": "address",   "description": "ReturnHeader/Filer/USAddress/AddressLine1Txt", "required": False},
    {"name": "org_city",              "type": "text",      "description": "ReturnHeader/Filer/USAddress/CityNm", "required": False},
    {"name": "org_state",             "type": "text",      "description": "ReturnHeader/Filer/USAddress/StateAbbreviationCd", "required": False},
    {"name": "org_zip",               "type": "text",      "description": "ReturnHeader/Filer/USAddress/ZIPCd", "required": False},
    {"name": "org_phone",             "type": "text",      "description": "ReturnHeader/Filer/PhoneNum", "required": False},
    {"name": "principal_officer",     "type": "name",      "description": "ReturnHeader/BusinessOfficerGrp/PersonNm — name of officer who signed", "required": False},
    {"name": "officer_title",         "type": "text",      "description": "ReturnHeader/BusinessOfficerGrp/PersonTitleTxt", "required": False},
    {"name": "officer_sign_date",     "type": "date",      "description": "ReturnHeader/BusinessOfficerGrp/SignatureDt", "required": False},
    {"name": "preparer_name",         "type": "name",      "description": "ReturnHeader/PreparerPersonGrp/PreparerPersonNm", "required": False},
    {"name": "preparer_ptin",         "type": "id_number", "description": "ReturnHeader/PreparerPersonGrp/PTIN", "required": False},
    {"name": "preparer_firm_name",    "type": "text",      "description": "ReturnHeader/PreparerFirmGrp/PreparerFirmName/BusinessNameLine1Txt", "required": False},
    {"name": "preparer_firm_ein",     "type": "id_number", "description": "ReturnHeader/PreparerFirmGrp/PreparerFirmEIN", "required": False},
    {"name": "preparer_firm_city",    "type": "text",      "description": "ReturnHeader/PreparerFirmGrp/PreparerUSAddress/CityNm", "required": False},
    {"name": "preparer_firm_state",   "type": "text",      "description": "ReturnHeader/PreparerFirmGrp/PreparerUSAddress/StateAbbreviationCd", "required": False},
]

F990_REVENUE = [
    {"name": "gross_receipts",               "type": "currency", "description": "IRS990/GrossReceiptsAmt — total gross receipts (not net revenue)", "required": False},
    {"name": "contributions_cy",             "type": "currency", "description": "IRS990/CYContributionsGrantsAmt — contributions and grants current year", "required": False},
    {"name": "contributions_py",             "type": "currency", "description": "IRS990/PYContributionsGrantsAmt — prior year", "required": False},
    {"name": "government_grants_cy",         "type": "currency", "description": "IRS990/GovernmentGrantsAmt — government grants included in contributions", "required": False},
    {"name": "program_service_revenue_cy",   "type": "currency", "description": "IRS990/CYProgramServiceRevenueAmt — program service revenue current year", "required": False},
    {"name": "program_service_revenue_py",   "type": "currency", "description": "IRS990/PYProgramServiceRevenueAmt", "required": False},
    {"name": "gross_ubi",                    "type": "currency", "description": "IRS990/TotalGrossUBIAmt — total gross unrelated business income (taxable activity)", "required": False},
    {"name": "investment_income_cy",         "type": "currency", "description": "IRS990/CYInvestmentIncomeAmt", "required": False},
    {"name": "other_revenue_cy",             "type": "currency", "description": "IRS990/CYOtherRevenueAmt", "required": False},
    {"name": "total_revenue_cy",             "type": "currency", "description": "IRS990/CYTotalRevenueAmt — total revenue current year", "required": True},
    {"name": "total_revenue_py",             "type": "currency", "description": "IRS990/PYTotalRevenueAmt — prior year total for year-over-year comparison", "required": False},
]

F990_EXPENSES = [
    {"name": "grants_paid_cy",               "type": "currency", "description": "IRS990/CYGrantsAndSimilarPaidAmt", "required": False},
    {"name": "member_benefits_cy",           "type": "currency", "description": "IRS990/CYBenefitsPaidToMembersAmt", "required": False},
    {"name": "salaries_cy",                  "type": "currency", "description": "IRS990/CYSalariesCompEmpBnftPaidAmt", "required": False},
    {"name": "salaries_py",                  "type": "currency", "description": "IRS990/PYSalariesCompEmpBnftPaidAmt", "required": False},
    {"name": "fundraising_expenses_cy",      "type": "currency", "description": "IRS990/CYTotalFundraisingExpenseAmt", "required": False},
    {"name": "total_expenses_cy",            "type": "currency", "description": "IRS990/CYTotalExpensesAmt", "required": True},
    {"name": "total_expenses_py",            "type": "currency", "description": "IRS990/PYTotalExpensesAmt", "required": False},
    {"name": "net_income_cy",                "type": "currency", "description": "IRS990/CYRevenuesLessExpensesAmt — revenue minus expenses", "required": False},
    {"name": "net_income_py",                "type": "currency", "description": "IRS990/PYRevenuesLessExpensesAmt", "required": False},
    {"name": "program_service_expenses",     "type": "currency", "description": "IRS990/TotalProgramServiceExpensesAmt", "required": False},
    # Expense line items from Part IX
    {"name": "exp_salaries_wages",           "type": "currency", "description": "IRS990/OtherSalariesAndWagesGrp/TotalAmt", "required": False},
    {"name": "exp_payroll_taxes",            "type": "currency", "description": "IRS990/PayrollTaxesGrp/TotalAmt", "required": False},
    {"name": "exp_legal_fees",               "type": "currency", "description": "IRS990/FeesForServicesLegalGrp/TotalAmt", "required": False},
    {"name": "exp_accounting_fees",          "type": "currency", "description": "IRS990/FeesForServicesAccountingGrp/TotalAmt", "required": False},
    {"name": "exp_advertising",              "type": "currency", "description": "IRS990/AdvertisingGrp/TotalAmt", "required": False},
    {"name": "exp_occupancy",                "type": "currency", "description": "IRS990/OccupancyGrp/TotalAmt", "required": False},
    {"name": "exp_travel",                   "type": "currency", "description": "IRS990/TravelGrp/TotalAmt", "required": False},
    {"name": "exp_depreciation",             "type": "currency", "description": "IRS990/DepreciationDepletionGrp/TotalAmt", "required": False},
    {"name": "exp_insurance",                "type": "currency", "description": "IRS990/InsuranceGrp/TotalAmt", "required": False},
]

F990_BALANCE_SHEET = [
    {"name": "total_assets_boy",             "type": "currency", "description": "IRS990/TotalAssetsBOYAmt — total assets beginning of year", "required": False},
    {"name": "total_assets_eoy",             "type": "currency", "description": "IRS990/TotalAssetsEOYAmt — total assets end of year", "required": True},
    {"name": "cash_eoy",                     "type": "currency", "description": "IRS990/CashNonInterestBearingGrp/EOYAmt", "required": False},
    {"name": "land_bldg_cost_basis",         "type": "currency", "description": "IRS990/LandBldgEquipCostOrOtherBssAmt — gross cost of land, buildings, equipment", "required": False},
    {"name": "land_bldg_accum_depreciation", "type": "currency", "description": "IRS990/LandBldgEquipAccumDeprecAmt", "required": False},
    {"name": "land_bldg_net_boy",            "type": "currency", "description": "IRS990/LandBldgEquipBasisNetGrp/BOYAmt — net book value of real property beginning of year", "required": False},
    {"name": "land_bldg_net_eoy",            "type": "currency", "description": "IRS990/LandBldgEquipBasisNetGrp/EOYAmt — net book value end of year", "required": False},
    {"name": "total_liabilities_boy",        "type": "currency", "description": "IRS990/TotalLiabilitiesGrp/BOYAmt", "required": False},
    {"name": "total_liabilities_eoy",        "type": "currency", "description": "IRS990/TotalLiabilitiesEOYAmt", "required": False},
    {"name": "net_assets_boy",               "type": "currency", "description": "IRS990/NetAssetsOrFundBalancesBOYAmt", "required": False},
    {"name": "net_assets_eoy",               "type": "currency", "description": "IRS990/NetAssetsOrFundBalancesEOYAmt", "required": True},
]

F990_ORG = [
    {"name": "mission_description",          "type": "text",    "description": "IRS990/ActivityOrMissionDesc or IRS990/MissionDesc — stated mission", "required": False},
    {"name": "program_description",          "type": "text",    "description": "IRS990/Desc — primary program service description", "required": False},
    {"name": "org_type_501c3",               "type": "boolean", "description": "IRS990/Organization501c3Ind — X if 501(c)(3)", "required": False},
    {"name": "num_board_members",            "type": "text",    "description": "IRS990/VotingMembersGoverningBodyCnt", "required": False},
    {"name": "num_independent_members",      "type": "text",    "description": "IRS990/VotingMembersIndependentCnt — 0 means all insiders, a major governance red flag", "required": False},
    {"name": "total_employees",              "type": "text",    "description": "IRS990/TotalEmployeeCnt", "required": False},
    {"name": "total_volunteers",             "type": "text",    "description": "IRS990/TotalVolunteersCnt", "required": False},
    {"name": "unrelated_business_income",    "type": "boolean", "description": "IRS990/UnrelatedBusIncmOverLimitInd — true if UBI exceeds threshold requiring 990T filing", "required": False},
    {"name": "form_990t_filed",              "type": "boolean", "description": "IRS990/Form990TFiledInd — whether 990T was filed for unrelated business income tax", "required": False},
]

F990_GOVERNANCE = [
    {"name": "gov_conflict_of_interest",     "type": "boolean", "description": "IRS990/ConflictOfInterestPolicyInd — does org have conflict of interest policy?", "required": False},
    {"name": "gov_whistleblower",            "type": "boolean", "description": "IRS990/WhistleblowerPolicyInd", "required": False},
    {"name": "gov_document_retention",       "type": "boolean", "description": "IRS990/DocumentRetentionPolicyInd", "required": False},
    {"name": "gov_ceo_compensation_process", "type": "boolean", "description": "IRS990/CompensationProcessCEOInd — independent process to set CEO pay?", "required": False},
    {"name": "gov_financial_audit",          "type": "boolean", "description": "IRS990/FSAuditedInd — financial statements independently audited?", "required": False},
    {"name": "gov_related_entity",           "type": "boolean", "description": "IRS990/RelatedEntityInd — does org have related entities? False when known related entities exist = SR-025 signal", "required": False},
    {"name": "gov_business_rln_org_members", "type": "boolean", "description": "IRS990/BusinessRlnWithOrgMemInd", "required": False},
    {"name": "gov_business_rln_family",      "type": "boolean", "description": "IRS990/BusinessRlnWithFamMemInd", "required": False},
    {"name": "gov_excess_benefit",           "type": "boolean", "description": "IRS990/EngagedInExcessBenefitTransInd", "required": False},
    {"name": "gov_loan_to_officer",          "type": "boolean", "description": "IRS990/LoanOutstandingInd", "required": False},
    {"name": "gov_grant_to_related",         "type": "boolean", "description": "IRS990/GrantToRelatedPersonInd", "required": False},
    {"name": "gov_transfer_non_charitable",  "type": "boolean", "description": "IRS990/TrnsfrExmptNonChrtblRltdOrgInd — transferred funds to non-charitable related org?", "required": False},
    {"name": "gov_990_provided_to_board",    "type": "boolean", "description": "IRS990/Form990ProvidedToGvrnBodyInd", "required": False},
]

# Officers — up to 10 (Part VII Section A)
F990_OFFICERS = _repeating("officer", 10, [
    ("name",              "name",     "IRS990/Form990PartVIISectionAGrp/PersonNm"),
    ("title",             "text",     "IRS990/Form990PartVIISectionAGrp/TitleTxt"),
    ("comp_from_org",     "currency", "IRS990/Form990PartVIISectionAGrp/ReportableCompFromOrgAmt — $0 on all officers is unusual for an org this size"),
    ("comp_from_related", "currency", "IRS990/Form990PartVIISectionAGrp/ReportableCompFromRltdOrgAmt"),
    ("hours_per_week",    "text",     "IRS990/Form990PartVIISectionAGrp/AverageHoursPerWeekRt"),
])

# Program service revenue lines — up to 8 (Part VIII)
F990_PROGRAM_REVENUE = _repeating("program_revenue", 8, [
    ("desc",              "text",     "IRS990/ProgramServiceRevenueGrp/Desc"),
    ("total",             "currency", "IRS990/ProgramServiceRevenueGrp/TotalRevenueColumnAmt"),
    ("ubi_amount",        "currency", "IRS990/ProgramServiceRevenueGrp/UnrelatedBusinessRevenueAmt — UBI portion triggers 990T"),
    ("related_amount",    "currency", "IRS990/ProgramServiceRevenueGrp/RelatedOrExemptFuncIncomeAmt"),
])

# Schedule A — public support
F990_SCHEDULE_A = [
    {"name": "sched_a_public_support_pct_cy", "type": "text",     "description": "IRS990ScheduleA/PublicSupportCY509Pct — 1.0 = 100% public support", "required": False},
    {"name": "sched_a_public_support_pct_py", "type": "text",     "description": "IRS990ScheduleA/PublicSupportPY509Pct", "required": False},
    {"name": "sched_a_public_support_total",  "type": "currency", "description": "IRS990ScheduleA/PublicSupportTotal509Amt", "required": False},
    {"name": "sched_a_type_509a2",            "type": "boolean",  "description": "IRS990ScheduleA/PubliclySupportedOrg509a2Ind — 509(a)(2) org derives support from program revenue", "required": False},
]

# Schedule D — supplemental financial statements (Part X detail)
F990_SCHEDULE_D = [
    {"name": "sched_d_land_book_value",       "type": "currency", "description": "IRS990ScheduleD/LandGrp/BookValueAmt", "required": False},
    {"name": "sched_d_buildings_cost",        "type": "currency", "description": "IRS990ScheduleD/OtherLandBuildingsGrp/OtherCostOrOtherBasisAmt", "required": False},
    {"name": "sched_d_buildings_depreciation","type": "currency", "description": "IRS990ScheduleD/OtherLandBuildingsGrp/DepreciationAmt", "required": False},
    {"name": "sched_d_buildings_book_value",  "type": "currency", "description": "IRS990ScheduleD/OtherLandBuildingsGrp/BookValueAmt", "required": False},
    {"name": "sched_d_total_buildings",       "type": "currency", "description": "IRS990ScheduleD/TotalBookValueLandBuildingsAmt", "required": False},
]

# Schedule L — related party transactions (up to 5)
F990_SCHEDULE_L = _repeating("related_txn", 5, [
    ("name",         "name",     "IRS990ScheduleL/TransactionsRelatedOrgGrp/NameOfInterested"),
    ("relationship", "text",     "IRS990ScheduleL/TransactionsRelatedOrgGrp/RelationshipWithOrganizationTxt"),
    ("description",  "text",     "IRS990ScheduleL/TransactionsRelatedOrgGrp/Desc"),
    ("amount",       "currency", "IRS990ScheduleL/TransactionsRelatedOrgGrp/TransactionAmt"),
])

# Schedule R — related organizations (up to 5)
F990_SCHEDULE_R = _repeating("related_org", 5, [
    ("name",         "name",     "IRS990ScheduleR — related organization name"),
    ("ein",          "id_number","IRS990ScheduleR — related organization EIN"),
    ("org_type",     "text",     "exempt, partnership, or corporation"),
    ("description",  "text",     "IRS990ScheduleR — primary activities or relationship description"),
])

# Schedule O — supplemental explanations (up to 10)
F990_SCHEDULE_O = _repeating("schedule_o", 10, [
    ("reference",    "text", "IRS990ScheduleO/SupplementalInformationDetail/FormAndLineReferenceDesc"),
    ("explanation",  "text", "IRS990ScheduleO/SupplementalInformationDetail/ExplanationTxt"),
])


F990_EXTRACTION_PROMPT = """Extract structured data from this IRS Form 990 XML filing.

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
- Financial fields specific to Form 990 will be null for 990T filings"""


def seed_990_schema(db):
    """Insert the IRS Form 990 schema if it doesn't already exist."""
    existing = db.query(DocumentSchema).filter(
        DocumentSchema.document_type == "990"
    ).first()

    if existing:
        print("990 schema already exists — skipping.")
        return existing

    schema_fields = _fields(
        F990_HEADER,
        F990_REVENUE,
        F990_EXPENSES,
        F990_BALANCE_SHEET,
        F990_ORG,
        F990_GOVERNANCE,
        F990_OFFICERS,
        F990_PROGRAM_REVENUE,
        F990_SCHEDULE_A,
        F990_SCHEDULE_D,
        F990_SCHEDULE_L,
        F990_SCHEDULE_R,
        F990_SCHEDULE_O,
    )

    schema = DocumentSchema(
        document_type="990",
        display_name="IRS Form 990 — Annual Return of Exempt Organization",
        vertical="fraud",
        schema_fields=schema_fields,
        extraction_prompt=F990_EXTRACTION_PROMPT,
        version=1,
        is_active=True,
    )
    db.add(schema)
    db.commit()
    db.refresh(schema)
    print(f"990 schema created — {len(schema_fields)} fields.")
    return schema


# ── SOS-FILING schema ─────────────────────────────────────────────────────────

SOS_CORE = [
    {"name": "entity_name",        "type": "name",      "description": "Legal entity name exactly as filed with the Secretary of State", "required": True},
    {"name": "entity_number",      "type": "id_number", "description": "SOS charter or registration number assigned to the entity", "required": True},
    {"name": "document_id",        "type": "id_number", "description": "Individual filing document ID for this specific instrument", "required": False},
    {"name": "filing_type",        "type": "text",      "description": "Type of SOS filing: Articles of Incorporation, Articles of Organization, Statement of Qualification, Continued Existence Notice, Charter Cancellation, Reinstatement, Amendment, Annual Report", "required": True},
    {"name": "entity_type",        "type": "text",      "description": "Legal structure: Nonprofit Corporation, For-Profit Corporation, LLC, LLP, LP, Trust", "required": True},
    {"name": "filing_date",        "type": "date",      "description": "Date the document was filed with the Secretary of State", "required": True},
    {"name": "effective_date",     "type": "date",      "description": "Effective date if different from filing date", "required": False},
    {"name": "filing_fee",         "type": "currency",  "description": "Fee paid to the SOS for this filing", "required": False},
    {"name": "state",              "type": "text",      "description": "State of formation or registration", "required": False},
    {"name": "county",             "type": "text",      "description": "County of principal office", "required": False},
    {"name": "sos_secretary",      "type": "name",      "description": "Name of Secretary of State who certified the filing — useful for dating documents", "required": False},
]

SOS_ADDRESSES = [
    {"name": "statutory_agent_name",    "type": "name",    "description": "Name of the statutory/registered agent", "required": False},
    {"name": "statutory_agent_address", "type": "address", "description": "Address of the statutory agent — this is the legal notice address for the entity", "required": False},
    {"name": "principal_office_address","type": "address", "description": "Principal office or business address", "required": False},
    {"name": "mailing_address",         "type": "address", "description": "Mailing or correspondence address on the receipt", "required": False},
    {"name": "receipt_addressee",       "type": "name",    "description": "Entity name or person on the filing receipt — may differ from legal entity name, revealing DBAs or related entities", "required": False},
]

# Named individuals — up to 5
SOS_PEOPLE = _repeating("person", 5, [
    ("name",    "name",    "Full name of individual as printed in the document"),
    ("role",    "text",    "Role: incorporator, organizer, statutory agent, member, manager, partner, officer, director, signatory"),
    ("address", "address", "Address given for this individual in the filing"),
])

SOS_FORMATION = [
    {"name": "purpose_description",  "type": "text",     "description": "Stated business purpose or mission — broad catch-all clauses vs. specific purposes are both significant", "required": False},
    {"name": "dissolution_clause",   "type": "text",     "description": "How assets are distributed on dissolution — for nonprofits, should specify 501(c)(3) recipients; vague clauses are a red flag", "required": False},
    {"name": "authorized_shares",    "type": "text",     "description": "Number and class of authorized shares (for-profit corps only)", "required": False},
    {"name": "initial_capital",      "type": "currency", "description": "Initial capital contribution stated in the articles", "required": False},
    {"name": "duration",             "type": "text",     "description": "Entity duration: perpetuity or stated term", "required": False},
    {"name": "law_firm_filer",       "type": "text",     "description": "Name of law firm or attorney that submitted the filing — repeated appearance of same firm across entities is a network signal", "required": False},
    {"name": "attorney_filer",       "type": "name",     "description": "Name of the individual attorney on the filing", "required": False},
    {"name": "formation_state",      "type": "text",     "description": "State of original formation (may differ from registration state for foreign entities)", "required": False},
]

SOS_STATUS = [
    {"name": "entity_status",           "type": "text",    "description": "Current status as shown on the document: Active, Cancelled, Suspended, Dissolved", "required": False},
    {"name": "cancellation_date",       "type": "date",    "description": "Date the charter or registration was cancelled", "required": False},
    {"name": "cancellation_reason",     "type": "text",    "description": "Stated reason for cancellation — failure to file continued existence, voluntary dissolution, etc.", "required": False},
    {"name": "reinstatement_date",      "type": "date",    "description": "Date reinstated after cancellation", "required": False},
    {"name": "reinstatement_fee",       "type": "currency","description": "Fee paid to reinstate", "required": False},
    {"name": "five_year_anniversary",   "type": "date",    "description": "For continued existence notices: the date by which the Statement of Continued Existence must be filed", "required": False},
    {"name": "advance_notice_date",     "type": "date",    "description": "Date the SOS sent the advance warning notice", "required": False},
    {"name": "original_formation_date", "type": "date",    "description": "Original incorporation/organization date — for amendment/reinstatement documents that reference it", "required": False},
]


SOS_EXTRACTION_PROMPT = """Extract structured data from this Ohio Secretary of State (SOS) filing document.

SOS FILING TYPES AND WHAT THEY CONTAIN:

Articles of Incorporation (Form 532B / C-101): Forms a nonprofit or for-profit corporation.
  - Contains: entity name, entity number, incorporators, statutory agent, purpose clause, dissolution clause, share structure
  - Key fields: who signed as incorporator, what address for statutory agent, dissolution language

Articles of Organization (Form 533A / 115-LCA): Forms an LLC.
  - Contains: entity name, entity number, organizer/member, statutory agent address
  - Note: LLC articles do NOT require a purpose clause or member list — operating agreement governs membership

Statement of Qualification (Form 536 / 105-PLL): Registers a Limited Liability Partnership.
  - Contains: entity name, partner/authorized signatory, chief executive office address
  - Note: No statutory agent required if Ohio CEO address is provided

Continued Existence Notice: SOS administrative letter warning that a nonprofit's 5-year filing is due.
  - Contains: entity name, entity number, deadline date, penalty for non-filing
  - The addressee's name and address is the statutory agent of record

Charter Cancellation: Certificate of cancellation issued by the SOS.
  - Contains: entity name, entity number, cancellation date, reason, reinstatement instructions

Reinstatement (Form 525B): Restores a cancelled entity.
  - Contains: entity name, entity number, reinstatement date, fee paid, signatory
  - IMPORTANT: The receipt addressee may name a DBA or related entity — always extract the receipt_addressee field

EXTRACTION RULES:

Entity name: Extract exactly as printed — preserve commas, periods, "Inc.", "LLC", "Ltd.", "LLP"

Named individuals: Extract EVERY person named anywhere in the document:
  - Incorporators, organizers, statutory agents, signatories, attorneys, partners
  - For each person: full name, role (how they appear in the document), and address if given
  - The same person may appear multiple times in different roles — extract each occurrence

Addresses: Two addresses often appear:
  - Statutory agent address: legal service address
  - Principal/CEO office: where business operates
  - Receipt/mailing address: where SOS sends correspondence — may differ from legal address

Law firm: Look for "filed by," "prepared by," or a firm name on the transmittal letter or receipt header.
  Repeated appearance of the same law firm across multiple entity filings is a network connection signal.

Dissolution clause (for nonprofits): The purpose attachment often contains language about how assets are
  distributed on dissolution. Extract this verbatim — it reveals whether specific recipient organizations
  are named or whether vague boilerplate was used.

Receipt addressee: The filing receipt may be addressed to a name different from the legal entity name.
  This can reveal DBAs, operating names, or related entities. Always capture this.

If a field is not present in this filing type, leave it null."""


def seed_sos_filing_schema(db):
    """Insert the SOS-FILING schema if it doesn't already exist."""
    existing = db.query(DocumentSchema).filter(
        DocumentSchema.document_type == "SOS-FILING"
    ).first()

    if existing:
        print("SOS-FILING schema already exists — skipping.")
        return existing

    schema_fields = _fields(
        SOS_CORE,
        SOS_ADDRESSES,
        SOS_PEOPLE,
        SOS_FORMATION,
        SOS_STATUS,
    )

    schema = DocumentSchema(
        document_type="SOS-FILING",
        display_name="Secretary of State Corporate Filing",
        vertical="fraud",
        schema_fields=schema_fields,
        extraction_prompt=SOS_EXTRACTION_PROMPT,
        version=1,
        is_active=True,
    )
    db.add(schema)
    db.commit()
    db.refresh(schema)
    print(f"SOS-FILING schema created — {len(schema_fields)} fields.")
    return schema


def main():
    db = SessionLocal()
    try:
        seed_parcel_record_schema(db)
        seed_deed_schema(db)
        seed_990_schema(db)
        seed_sos_filing_schema(db)
    finally:
        db.close()


if __name__ == "__main__":
    main()
