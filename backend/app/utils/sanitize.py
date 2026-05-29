"""
Shared sanitization helpers for the HTTP boundary.

escape_csv_cell()      — neutralizes spreadsheet formula injection in CSV exports.
safe_header_filename() — strips control chars so filenames can't inject HTTP headers.
content_disposition()  — builds a CRLF-safe Content-Disposition with ASCII + RFC 5987 names.
"""
from urllib.parse import quote

# Leading characters that trigger formula evaluation in Excel / Google Sheets.
_CSV_FORMULA_TRIGGERS = ("=", "+", "-", "@", "\t", "\r")


def escape_csv_cell(value) -> str:
    """Return value as a CSV-safe string, neutralizing formula injection.

    If the stringified value begins with a formula trigger (= + - @ tab CR),
    prefix it with a single quote so spreadsheet apps treat it as text.
    None becomes an empty string.
    """
    if value is None:
        return ""
    text = str(value)
    if text and text[0] in _CSV_FORMULA_TRIGGERS:
        return "'" + text
    return text


def safe_header_filename(name: str) -> str:
    """Return an ASCII-safe filename fragment for a Content-Disposition header.

    Removes control characters (including CR/LF), double quotes, and backslashes
    that could break out of the quoted filename parameter or inject a header.
    Falls back to "download" if nothing usable remains.
    """
    if not name:
        return "download"
    cleaned = "".join(c for c in name if c.isprintable() and c not in '"\\')
    cleaned = cleaned.strip()
    return cleaned or "download"


def content_disposition(filename: str, disposition: str = "attachment") -> str:
    """Build a CRLF-safe Content-Disposition header value.

    Emits both an ASCII `filename="..."` (control-stripped) and an RFC 5987
    `filename*=UTF-8''<percent-encoded>` so user-controlled names cannot inject
    headers while still round-tripping unicode where the client supports it.
    """
    ascii_name = safe_header_filename(filename)
    encoded = quote(filename or "download", safe="")
    return f"{disposition}; filename=\"{ascii_name}\"; filename*=UTF-8''{encoded}"
