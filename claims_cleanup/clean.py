"""Pure cleaning, normalization, and validation functions (no file I/O)."""

from datetime import datetime

# Accepted input formats, tried in order. Slash dates are DAY-FIRST (DD/MM/YYYY),
# matching the source data's locale — never left to a library's locale guess.
_DATE_FORMATS = [("%Y-%m-%d", False), ("%d/%m/%Y", True), ("%B %d, %Y", True), ("%b %d, %Y", True)]


def parse_amount(raw):
    """Parse a submitted amount.

    Returns (value, issues). `value` is a float, or None if unparseable.
    `issues` may contain "amount_comma_format" (commas were stripped) and/or
    "invalid_amount" (non-numeric, negative, or zero).
    """
    issues = []
    if raw is None:
        return None, ["invalid_amount"]
    s = str(raw).strip()
    if "," in s:
        issues.append("amount_comma_format")
        s = s.replace(",", "")
    try:
        value = float(s)
    except ValueError:
        return None, ["invalid_amount"]
    if value <= 0:
        issues.append("invalid_amount")
    return value, issues


def parse_date(raw):
    """Parse a date to ISO 8601 (YYYY-MM-DD).

    Returns (iso_string, issues). Tries each accepted format in order; a non-ISO
    match is flagged "date_format_variant". Unparseable or impossible dates
    (e.g. 31/02/2024) return (None, ["invalid_date"]).
    """
    if raw is None:
        return None, ["invalid_date"]
    s = str(raw).strip()
    for fmt, is_variant in _DATE_FORMATS:
        try:
            dt = datetime.strptime(s, fmt)
        except ValueError:
            continue
        return dt.strftime("%Y-%m-%d"), (["date_format_variant"] if is_variant else [])
    return None, ["invalid_date"]
