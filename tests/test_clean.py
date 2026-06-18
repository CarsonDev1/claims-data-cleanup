from claims_cleanup.clean import parse_amount, parse_date


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
