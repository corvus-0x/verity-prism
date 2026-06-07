import pytest
from app.services.extraction_engine import _normalize_field_value


# ── Currency ─────────────────────────────────────────────────────────────────

def test_currency_strips_dollar_and_commas():
    assert _normalize_field_value("$1,250,000.00", "currency") == "1250000.00"


def test_currency_already_plain_integer():
    assert _normalize_field_value("625000", "currency") == "625000.00"


def test_currency_range_takes_first_value():
    assert _normalize_field_value("$100,000 - $150,000", "currency") == "100000.00"


def test_currency_unparseable_returns_original():
    assert _normalize_field_value("N/A", "currency") == "N/A"


def test_currency_multiplier_suffix_returns_original():
    # "1.5M" should NOT silently truncate to "1.50" — return original unchanged
    assert _normalize_field_value("1.5M", "currency") == "1.5M"
    assert _normalize_field_value("$2.3B", "currency") == "$2.3B"


def test_currency_zero():
    assert _normalize_field_value("$0.00", "currency") == "0.00"


# ── Date ──────────────────────────────────────────────────────────────────────

def test_date_slash_mm_dd_yyyy():
    assert _normalize_field_value("01/05/2026", "date") == "2026-01-05"


def test_date_long_month_format():
    assert _normalize_field_value("January 5, 2026", "date") == "2026-01-05"


def test_date_abbreviated_month():
    assert _normalize_field_value("Jan 5, 2026", "date") == "2026-01-05"


def test_date_already_iso():
    assert _normalize_field_value("2026-01-05", "date") == "2026-01-05"


def test_date_unparseable_returns_original():
    assert _normalize_field_value("sometime in 2026", "date") == "sometime in 2026"


# ── Boolean ───────────────────────────────────────────────────────────────────

def test_boolean_truthy_variants():
    for v in ("yes", "YES", "True", "TRUE", "1", "y", "t"):
        assert _normalize_field_value(v, "boolean") == "true", f"Expected 'true' for '{v}'"


def test_boolean_falsy_variants():
    for v in ("no", "NO", "false", "FALSE", "0", "n"):
        assert _normalize_field_value(v, "boolean") == "false", f"Expected 'false' for '{v}'"


# ── Text / pass-through ────────────────────────────────────────────────────────

def test_text_strips_whitespace_only():
    assert _normalize_field_value("  Oak Ridge LLC  ", "text") == "Oak Ridge LLC"


def test_name_strips_whitespace():
    assert _normalize_field_value("  John Smith  ", "name") == "John Smith"


def test_address_strips_whitespace():
    assert _normalize_field_value("  123 Main St  ", "address") == "123 Main St"


# ── Edge cases ─────────────────────────────────────────────────────────────────

def test_none_returns_none():
    assert _normalize_field_value(None, "currency") is None


def test_none_returns_none_for_date():
    assert _normalize_field_value(None, "date") is None


def test_empty_string_returns_empty():
    assert _normalize_field_value("   ", "text") == ""
