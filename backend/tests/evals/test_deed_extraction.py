"""
Extraction quality evals for the DEED document type.

These tests call the real Claude API — run separately from unit tests:
    docker-compose run --rm \
        -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test \
        backend pytest tests/evals/ -v -m eval

Each case provides realistic deed OCR text and checks extract_fields()
returns correct values for the 7 required fields.
"""
import re
import uuid
import pytest
from app.models.document_schema import DocumentSchema
from app.services.extraction_engine import extract_fields


DEED_REQUIRED_FIELDS = [
    {"name": "instrument_number", "type": "id_number", "required": True,
     "description": "Official instrument/recording number assigned by the county recorder"},
    {"name": "recording_date",    "type": "date",      "required": True,
     "description": "Date the instrument was recorded with the county recorder"},
    {"name": "recording_county",  "type": "text",      "required": True,
     "description": "County where the deed was recorded"},
    {"name": "deed_type",         "type": "text",      "required": True,
     "description": "Type of deed: WARRANTY DEED, QUITCLAIM DEED, FIDUCIARY DEED, etc."},
    {"name": "grantor_name",      "type": "name",      "required": True,
     "description": "Full legal name of the grantor (seller/transferor)"},
    {"name": "grantee_name",      "type": "name",      "required": True,
     "description": "Full legal name of the grantee (buyer/recipient)"},
    {"name": "legal_description", "type": "text",      "required": True,
     "description": "Full verbatim legal description of the property being conveyed"},
]

CASES = [
    {
        "id": "warranty_residential",
        "description": "Standard residential warranty deed",
        "ocr_text": """
INSTRUMENT NO. 202308140045
RECORDED: August 14, 2023  10:46 AM
TULSA COUNTY, OKLAHOMA
RECORDING FEE: $18.00  PAGES: 3

WARRANTY DEED

THIS WARRANTY DEED, made and entered into this 10th day of August, 2023,

GRANTOR: Robert J. Henderson, a married man, of 1204 Birchwood Lane,
Tulsa, Oklahoma 74106

GRANTEE: Sarah M. Kowalski, a single woman, whose mailing address is
2847 Maple Grove Drive, Tulsa, Oklahoma 74105

WITNESSETH, that the Grantor, for and in consideration of TEN DOLLARS ($10.00)
and other valuable consideration, does hereby grant, bargain, sell and convey
unto the Grantee the following described real property situated in Tulsa County,
State of Oklahoma, to-wit:

Lot 14, Block 3, MAPLE GROVE SUBDIVISION, an addition to the City of Tulsa,
Tulsa County, Oklahoma, according to the recorded plat thereof in Book 52, Page 18.

Property Address: 2847 Maple Grove Drive, Tulsa, Oklahoma 74105

IN WITNESS WHEREOF, the Grantor has executed this deed on the date first above written.

Robert J. Henderson
Notary: Patricia A. Simmons  Commission Expires: 06/15/2026
Prepared by: James R. Whitfield, Attorney, 411 S. Boulder Ave., Tulsa OK
""",
        "expected": {
            "instrument_number": "202308140045",
            "recording_date":    "2023-08-14",
            "recording_county":  "Tulsa",
            "deed_type":         "WARRANTY DEED",
            "grantor_name":      "Robert J. Henderson",
            "grantee_name":      "Sarah M. Kowalski",
            "legal_description": "non_null",
        },
    },
    {
        "id": "quitclaim_trust_to_llc",
        "description": "Quitclaim from revocable trust to LLC — common fraud pattern",
        "ocr_text": """
INSTRUMENT NO. 202401220012
FILED: January 22, 2024  2:15 PM
TULSA COUNTY, OKLAHOMA
RECORDING FEE: $13.00  PAGES: 2
CONVEYANCE FEE: EXEMPT  Code: EL

QUITCLAIM DEED

Thompson Family Revocable Trust, Dated March 12, 2008, Douglas R. Thompson,
Trustee ("Grantor"), for good and valuable consideration, the receipt of which
is hereby acknowledged, does hereby REMISE, RELEASE AND QUITCLAIM unto
Horizon Properties LLC, an Oklahoma limited liability company ("Grantee"),
whose mailing address is P.O. Box 4412, Tulsa, Oklahoma 74101, all right,
title, interest, claim and demand of Grantor in and to the following described
real property in Tulsa County, Oklahoma:

Lots 7 and 8, Block 11, RIVERSIDE HEIGHTS ADDITION to the City of Tulsa,
Tulsa County, Oklahoma, as per the recorded plat thereof.

Instrument executed this 18th day of January, 2024.
Thompson Family Revocable Trust, Douglas R. Thompson, Trustee

Notary: Kevin M. Ortiz  Expires: 09/30/2025
Prepared by: Horizon Legal Group, 800 W. 6th St., Tulsa OK 74119
""",
        "expected": {
            "instrument_number": "202401220012",
            "recording_date":    "2024-01-22",
            "recording_county":  "Tulsa",
            "deed_type":         "QUITCLAIM DEED",
            "grantor_name":      "Thompson Family Revocable Trust",
            "grantee_name":      "Horizon Properties LLC",
            "legal_description": "non_null",
        },
    },
    {
        "id": "fiduciary_estate",
        "description": "Fiduciary deed from estate personal representative",
        "ocr_text": """
OFFICIAL RECORD
INSTRUMENT NUMBER: 202209060098
RECORDING DATE: September 6, 2022
CREEK COUNTY, OKLAHOMA
FEE PAID: $18.00

FIDUCIARY DEED

Estate of Margaret Louise Carpenter, Deceased, by and through its duly appointed
Personal Representative, William T. Carpenter, whose address is 644 Elm Street,
Sapulpa, Oklahoma 74066, as GRANTOR,

does hereby convey to First National Property Holdings LLC, an Oklahoma limited
liability company, P.O. Box 1102, Tulsa, Oklahoma 74101, as GRANTEE,

for and in consideration of valuable consideration paid, the following described
real property situated in Creek County, Oklahoma:

Beginning at the Northeast corner of the Southeast Quarter (SE/4) of Section 14,
Township 18 North, Range 12 East; thence South 660 feet; thence West 330 feet;
thence North 660 feet; thence East 330 feet to the point of beginning,
containing 5 acres more or less.

Executed this 1st day of September, 2022.
William T. Carpenter, Personal Representative, Estate of Margaret Louise Carpenter

Notary: Sandra G. Flores  Commission No. 10047892  Expires: 12/31/2024
Prepared by: Dale H. Morrison, Attorney, 112 N. Mission St., Sapulpa OK
""",
        "expected": {
            "instrument_number": "202209060098",
            "recording_date":    "2022-09-06",
            "recording_county":  "Creek",
            "deed_type":         "FIDUCIARY DEED",
            "grantor_name":      "Estate of Margaret Louise Carpenter",
            "grantee_name":      "First National Property Holdings LLC",
            "legal_description": "non_null",
        },
    },
]


# ── Scoring helpers ──────────────────────────────────────────────────────────

_MONTH_MAP = {
    "january": "01", "february": "02", "march": "03", "april": "04",
    "may": "05", "june": "06", "july": "07", "august": "08",
    "september": "09", "october": "10", "november": "11", "december": "12",
}


def _normalize_date(value: str | None) -> str | None:
    """Convert common date formats to YYYY-MM-DD. Returns None on failure."""
    if not value:
        return None
    v = value.strip()

    # Already ISO: 2023-08-14
    if re.match(r"^\d{4}-\d{2}-\d{2}$", v):
        return v

    # MM/DD/YYYY or MM-DD-YYYY
    m = re.match(r"^(\d{1,2})[/-](\d{1,2})[/-](\d{4})$", v)
    if m:
        return f"{m.group(3)}-{m.group(1).zfill(2)}-{m.group(2).zfill(2)}"

    # "August 14, 2023" or "14 August 2023"
    m = re.match(
        r"^(?:(\w+)\s+(\d{1,2}),?\s+(\d{4})|(\d{1,2})\s+(\w+)\s+(\d{4}))$", v, re.I
    )
    if m:
        if m.group(1):
            month_name, day, year = m.group(1), m.group(2), m.group(3)
        else:
            day, month_name, year = m.group(4), m.group(5), m.group(6)
        month = _MONTH_MAP.get(month_name.lower())
        if month:
            return f"{year}-{month}-{day.zfill(2)}"

    return v


def _norm(value: str | None) -> str:
    return (value or "").strip().lower()


def score_field(field: str, actual: str | None, expected: str | None) -> bool:
    if expected == "non_null":
        return bool(actual and actual.strip())

    if field == "recording_date":
        return _normalize_date(actual) == _normalize_date(expected)

    if field in ("grantor_name", "grantee_name"):
        # Allow the expected name to appear within a longer actual value
        # e.g. actual="Thompson Family Revocable Trust, Douglas R. Thompson, Trustee"
        a, e = _norm(actual), _norm(expected)
        return a == e or e in a

    if field == "recording_county":
        # Claude often returns "Tulsa County, Oklahoma" — strip state and "County" suffix
        def _strip_county(v: str) -> str:
            v = re.sub(r",?\s*(oklahoma|ok|ohio|oh|texas|tx)\s*$", "", v, flags=re.I)
            v = re.sub(r"\s+county\s*$", "", v, flags=re.I)
            return v.strip().lower()
        return _strip_county(actual or "") == _strip_county(expected or "")

    return _norm(actual) == _norm(expected)


# ── Tests ────────────────────────────────────────────────────────────────────

@pytest.fixture
def deed_schema(db):
    schema = DocumentSchema(
        id=str(uuid.uuid4()),
        document_type="DEED",
        display_name="Deed (Eval)",
        vertical="general",
        schema_fields=DEED_REQUIRED_FIELDS,
        extraction_prompt=(
            "You are extracting fields from an Oklahoma county recorder deed. "
            "Extract exactly the fields listed. Return null for any field not present."
        ),
        version=1,
        is_active=True,
        parse_strategy="claude",
        default_confidence_threshold=0.85,
    )
    db.add(schema)
    db.commit()
    return schema


@pytest.mark.eval
@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_deed_required_fields(case, deed_schema):
    """Run extract_fields() and verify all required fields for a deed case."""
    extractions = extract_fields(case["ocr_text"], deed_schema)
    by_field = {e["field_name"]: e.get("field_value") for e in extractions}

    results = {
        field: score_field(field, by_field.get(field), expected_val)
        for field, expected_val in case["expected"].items()
    }

    print(f"\n── {case['id']} ──")
    for field, passed in results.items():
        actual = by_field.get(field)
        expected = case["expected"][field]
        icon = "✓" if passed else "✗"
        print(f"  {icon} {field}: {actual!r}  (expected: {expected!r})")

    total = len(results)
    passed_count = sum(results.values())
    print(f"  Score: {passed_count}/{total}")

    failed = [f for f, ok in results.items() if not ok]
    assert not failed, f"Fields failed: {failed}"
