from claims_cleanup.clean import (
    parse_amount, parse_date, normalize_null, normalize_name,
    map_claim_type, map_currency, validate_status, clean_dataset,
)


def _row(**kw):
    base = dict(claim_id="CLM-00001", policy_id="POL-1", member_name="John Doe",
                claim_type="OUTPATIENT", diagnosis="Flu", submitted_amount="2500",
                currency="THB", submitted_date="2024-03-15", status="APPROVED")
    base.update(kw)
    return base


def test_parses_plain_number():
    assert parse_amount("15000") == (15000.0, [])


def test_parses_comma_string_and_flags_format():
    assert parse_amount("15,000") == (15000.0, ["amount_comma_format"])


def test_negative_is_invalid():
    assert parse_amount("-5") == (-5.0, ["invalid_amount"])


def test_zero_is_invalid():
    assert parse_amount("0") == (0.0, ["invalid_amount"])


def test_nonnumeric_is_invalid_none():
    assert parse_amount("abc") == (None, ["invalid_amount"])


def test_accepts_numeric_type():
    assert parse_amount(2500) == (2500.0, [])


def test_iso_passthrough_no_issue():
    assert parse_date("2024-03-15") == ("2024-03-15", [])


def test_slash_is_day_first():
    assert parse_date("15/03/2024") == ("2024-03-15", ["date_format_variant"])


def test_ambiguous_slash_uses_day_first():
    assert parse_date("03/04/2024") == ("2024-04-03", ["date_format_variant"])


def test_long_format():
    assert parse_date("March 15, 2024") == ("2024-03-15", ["date_format_variant"])


def test_impossible_date_flagged():
    assert parse_date("31/02/2024") == (None, ["invalid_date"])


def test_garbage_flagged():
    assert parse_date("not a date") == (None, ["invalid_date"])


def test_normalize_null_variants():
    assert normalize_null("N/A") is None
    assert normalize_null("n/a") is None
    assert normalize_null("") is None
    assert normalize_null("  Flu ") == "Flu"


def test_name_titlecase_flags_change():
    assert normalize_name("JOHN DOE") == ("John Doe", ["name_casing"])
    assert normalize_name("John Doe") == ("John Doe", [])


def test_claim_type_typo_mapped():
    assert map_claim_type("Outpateint") == ("OUTPATIENT", ["claim_type_typo"])
    assert map_claim_type("OP") == ("OUTPATIENT", ["claim_type_typo"])
    assert map_claim_type("OUTPATIENT") == ("OUTPATIENT", [])
    assert map_claim_type("xyz") == (None, ["claim_type_typo"])


def test_currency_variants():
    assert map_currency("Baht") == ("THB", ["currency_variant"])
    assert map_currency("vnd") == ("VND", ["currency_variant"])
    assert map_currency("THB") == ("THB", [])
    assert map_currency("eur") == (None, ["currency_variant"])


def test_status_enum():
    assert validate_status("approved") == ("APPROVED", [])
    assert validate_status("APPROVED") == ("APPROVED", [])
    assert validate_status("weird") == (None, ["status_out_of_enum"])


def test_exact_duplicates_removed_and_counted():
    r = clean_dataset([_row(), _row()])
    assert r.duplicates_removed == 1 and len(r.clean_rows) == 1
    assert any(i.issue_type == "exact_duplicate_row" for i in r.detected_issues)


def test_invalid_amount_quarantined_not_in_clean():
    r = clean_dataset([_row(submitted_amount="-10")])
    assert len(r.clean_rows) == 0 and len(r.quarantine_rows) == 1
    assert r.quarantine_rows[0]["quarantine_reason"] == "invalid_amount"


def test_invalid_date_flagged_but_kept_in_clean():
    # Per the brief, only invalid amounts are removed; an unparseable date is
    # flagged and the row kept, with the date normalized to null.
    r = clean_dataset([_row(submitted_date="31/02/2024")])
    assert len(r.clean_rows) == 1 and len(r.quarantine_rows) == 0
    assert r.clean_rows[0]["submitted_date"] is None
    assert any(i.issue_type == "invalid_date" for i in r.detected_issues)


def test_duplicate_claim_id_flagged_but_kept():
    r = clean_dataset([_row(claim_id="CLM-9"), _row(claim_id="CLM-9", member_name="Jane Roe")])
    assert len(r.clean_rows) == 2  # different data -> both kept
    assert sum(i.issue_type == "duplicate_claim_id" for i in r.detected_issues) >= 1


def test_comma_amount_cleaned_to_number():
    r = clean_dataset([_row(submitted_amount="15,000")])
    assert r.clean_rows[0]["submitted_amount"] == 15000.0
    assert any(i.issue_type == "amount_comma_format" for i in r.detected_issues)


def test_reconciliation_invariant():
    rows = [_row(), _row(), _row(submitted_amount="0"), _row(claim_id="CLM-2", member_name="A B")]
    r = clean_dataset(rows)
    assert r.rows_before == len(r.clean_rows) + r.duplicates_removed + len(r.quarantine_rows)
