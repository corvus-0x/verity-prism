from app.utils.sanitize import escape_csv_cell, safe_header_filename, content_disposition


def test_escape_csv_cell_neutralizes_formula_triggers():
    assert escape_csv_cell("=cmd()") == "'=cmd()"
    assert escape_csv_cell("+1+1") == "'+1+1"
    assert escape_csv_cell("-2") == "'-2"
    assert escape_csv_cell("@SUM(A1)") == "'@SUM(A1)"
    assert escape_csv_cell("\tx") == "'\tx"


def test_escape_csv_cell_passes_safe_values():
    assert escape_csv_cell("John Smith") == "John Smith"
    assert escape_csv_cell("285000") == "285000"


def test_escape_csv_cell_handles_none():
    assert escape_csv_cell(None) == ""


def test_safe_header_filename_strips_crlf_and_quotes():
    out = safe_header_filename('evil\r\nSet-Cookie: x".pdf')
    assert "\r" not in out
    assert "\n" not in out
    assert '"' not in out


def test_safe_header_filename_empty_fallback():
    assert safe_header_filename("") == "download"
    assert safe_header_filename("\r\n") == "download"


def test_content_disposition_crlf_free_with_both_params():
    value = content_disposition("a\r\nb.csv", "attachment")
    assert "\r" not in value
    assert "\n" not in value
    assert value.startswith("attachment;")
    assert "filename=" in value
    assert "filename*=UTF-8''" in value


def test_content_disposition_inline_type():
    value = content_disposition("report.pdf", "inline")
    assert value.startswith("inline;")
