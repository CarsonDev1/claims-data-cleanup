"""Pure cleaning, normalization, and validation functions (no file I/O)."""

from datetime import datetime

from claims_cleanup.constants import CLAIM_TYPES, CLAIM_TYPE_MAP, CURRENCY_MAP, STATUSES

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


def normalize_null(raw):
    """Collapse "N/A"/"n/a"/empty to None; otherwise return the trimmed string."""
    if raw is None:
        return None
    s = str(raw).strip()
    return None if s == "" or s.lower() == "n/a" else s


def normalize_name(raw):
    """Title-case a member name; flag "name_casing" if the input differed."""
    s = normalize_null(raw)
    if s is None:
        return None, []
    titled = s.title()
    return titled, ([] if titled == s else ["name_casing"])


def map_claim_type(raw):
    """Map a claim type to its canonical enum value; flag "claim_type_typo" if remapped or unknown."""
    s = normalize_null(raw)
    if s is None:
        return None, ["claim_type_typo"]
    if s in CLAIM_TYPES:
        return s, []
    canon = CLAIM_TYPE_MAP.get(s.lower())
    return (canon, ["claim_type_typo"]) if canon else (None, ["claim_type_typo"])


def map_currency(raw):
    """Map a currency to uppercase ISO; flag "currency_variant" if remapped or unknown."""
    s = normalize_null(raw)
    if s is None:
        return None, ["currency_variant"]
    canon = CURRENCY_MAP.get(s.lower())
    if canon is None:
        return None, ["currency_variant"]
    return canon, ([] if s == canon else ["currency_variant"])


def validate_status(raw):
    """Uppercase + validate status against the enum; flag "status_out_of_enum" if invalid."""
    s = normalize_null(raw)
    up = s.upper() if s else None
    return (up, []) if up in STATUSES else (None, ["status_out_of_enum"])
