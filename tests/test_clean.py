from claims_cleanup.clean import parse_amount


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
