"""Pure cleaning, normalization, and validation functions (no file I/O)."""

from collections import Counter
from dataclasses import dataclass
from datetime import datetime

from claims_cleanup.constants import CLAIM_TYPES, CLAIM_TYPE_MAP, COLUMNS, CURRENCY_MAP, STATUSES

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


@dataclass
class DetectedIssue:
    row_index: int
    issue_type: str


@dataclass
class CleanResult:
    clean_rows: list
    quarantine_rows: list
    detected_issues: list
    duplicates_removed: int
    rows_before: int


def clean_dataset(rows):
    """Clean a list of raw row dicts and return a CleanResult.

    Order: trim -> drop exact-duplicate rows (counted) -> per-row normalize and
    validate (collecting issues) -> flag duplicate claim_ids (kept, not removed) ->
    quarantine rows with an invalid amount or an unparseable date.
    """
    rows_before = len(rows)
    trimmed = [{k: (v.strip() if isinstance(v, str) else v) for k, v in r.items()} for r in rows]

    # 1. exact duplicates: keep first occurrence, drop and count the rest
    seen, kept, dup_count, issues = set(), [], 0, []
    for idx, r in enumerate(trimmed):
        key = tuple(r.get(c) for c in COLUMNS)
        if key in seen:
            dup_count += 1
            issues.append(DetectedIssue(idx, "exact_duplicate_row"))
        else:
            seen.add(key)
            kept.append((idx, r))

    # 2. duplicate claim_id among kept rows (different data) -> flag but keep
    id_counts = Counter(r.get("claim_id") for _, r in kept if r.get("claim_id"))

    clean_rows, quarantine_rows = [], []
    for idx, r in kept:
        out, reasons = {}, []
        cid = r.get("claim_id")
        if not cid:
            reasons.append("missing_claim_id")
        elif id_counts[cid] > 1:
            reasons.append("duplicate_claim_id")
        out["claim_id"] = cid or None
        out["policy_id"] = r.get("policy_id") or None
        if not out["policy_id"]:
            reasons.append("missing_policy_id")
        out["member_name"], ni = normalize_name(r.get("member_name"))
        reasons += ni
        out["claim_type"], ci = map_claim_type(r.get("claim_type"))
        reasons += ci
        diag = normalize_null(r.get("diagnosis"))
        out["diagnosis"] = diag
        if diag is None:
            reasons.append("missing_diagnosis")
        amt, ai = parse_amount(r.get("submitted_amount"))
        out["submitted_amount"] = amt
        reasons += ai
        out["currency"], cui = map_currency(r.get("currency"))
        reasons += cui
        dt, di = parse_date(r.get("submitted_date"))
        out["submitted_date"] = dt
        reasons += di
        out["status"], si = validate_status(r.get("status"))
        reasons += si

        for reason in reasons:
            issues.append(DetectedIssue(idx, reason))

        # quarantine unusable records (audit trail) rather than dropping them
        if amt is None or "invalid_amount" in reasons:
            quarantine_rows.append({**out, "quarantine_reason": "invalid_amount"})
        elif dt is None:
            quarantine_rows.append({**out, "quarantine_reason": "invalid_date"})
        else:
            clean_rows.append(out)

    return CleanResult(clean_rows, quarantine_rows, issues, dup_count, rows_before)
