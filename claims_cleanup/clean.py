"""Pure cleaning, normalization, and validation functions (no file I/O)."""


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
