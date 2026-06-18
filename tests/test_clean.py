from claims_cleanup.clean import (
    parse_amount, parse_date, normalize_null, normalize_name,
    map_claim_type, map_currency, validate_status,
)


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
