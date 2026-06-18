from claims_cleanup.generate import generate_dataset
from claims_cleanup.constants import COLUMNS, ISSUE_TYPES


def test_deterministic():
    a, ga = generate_dataset(42)
    b, gb = generate_dataset(42)
    assert a == b and ga == gb


def test_row_count_and_columns():
    rows, _ = generate_dataset(42, n=500)
    assert len(rows) >= 500  # exact/duplicate-id injections append a few rows
    assert all(set(r.keys()) == set(COLUMNS) for r in rows)


def test_issue_rate_in_range():
    rows, gt = generate_dataset(42, n=500)
    affected = {g["row_index"] for g in gt}
    rate = len(affected) / len(rows)
    assert 0.13 <= rate <= 0.22, rate


def test_all_issue_types_present():
    _, gt = generate_dataset(42, n=500)
    present = {g["issue_type"] for g in gt}
    required = set(ISSUE_TYPES) - {"status_out_of_enum"}  # status issue is optional
    assert required.issubset(present), required - present
