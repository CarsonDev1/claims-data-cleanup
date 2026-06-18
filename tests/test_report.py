from claims_cleanup.clean import clean_dataset
from claims_cleanup.report import build_report, render_markdown


def _row(**kw):
    base = dict(claim_id="CLM-1", policy_id="POL-1", member_name="A B", claim_type="OUTPATIENT",
                diagnosis="Flu", submitted_amount="100", currency="THB",
                submitted_date="2024-01-02", status="APPROVED")
    base.update(kw)
    return base


def test_reconciliation_and_counts():
    rows = [_row(claim_id="CLM-1"), _row(claim_id="CLM-1"),       # exact dup
            _row(claim_id="CLM-2", submitted_amount="0"),          # quarantine
            _row(claim_id="CLM-3", currency="VND", submitted_amount="200")]
    rep = build_report(clean_dataset(rows))
    assert rep["rows_before"] == rep["rows_after"] + rep["duplicates_removed"] + rep["quarantined"]
    assert rep["duplicates_removed"] == 1 and rep["quarantined"] == 1


def test_avg_amount_split_by_currency():
    rows = [_row(claim_id="CLM-1", currency="THB", submitted_amount="100"),
            _row(claim_id="CLM-2", currency="VND", submitted_amount="900")]
    rep = build_report(clean_dataset(rows))
    assert rep["avg_amount_by_type_currency"][("OUTPATIENT", "THB")] == 100.0
    assert rep["avg_amount_by_type_currency"][("OUTPATIENT", "VND")] == 900.0


def test_top_diagnoses_excludes_null_and_normalizes_case():
    rows = [_row(claim_id=f"CLM-{i}", diagnosis=d)
            for i, d in enumerate(["Flu", "flu", "N/A", "Migraine"])]
    rep = build_report(clean_dataset(rows))
    names = [n for n, _ in rep["top_diagnoses"]]
    counts = dict(rep["top_diagnoses"])
    assert "Flu" in names and "N/A" not in names and None not in names
    assert counts["Flu"] == 2  # "Flu" and "flu" merged case-insensitively


def test_render_markdown_has_sections():
    rep = build_report(clean_dataset([_row()]))
    md = render_markdown(rep)
    for heading in ["# Data Quality Report", "Rows before", "Issues by type", "Top 5 diagnoses"]:
        assert heading in md
