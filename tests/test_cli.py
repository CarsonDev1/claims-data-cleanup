import csv
import json
import subprocess
import sys


def _read_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def test_pipeline_end_to_end(tmp_path):
    data_dir = tmp_path / "data"
    report_dir = tmp_path / "reports"
    result = subprocess.run(
        [sys.executable, "-m", "claims_cleanup.cli", "all",
         "--seed", "42", "--data-dir", str(data_dir), "--report-dir", str(report_dir)],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "VERIFY OK" in result.stdout

    dirty = _read_csv(data_dir / "claims_dirty.csv")
    clean = _read_csv(data_dir / "claims_clean.csv")
    quarantine = _read_csv(data_dir / "claims_quarantine.csv")
    summary = json.loads((data_dir / "_report.json").read_text(encoding="utf-8"))

    assert len(dirty) >= 500
    # reconciliation: every dirty row is accounted for
    assert len(dirty) == len(clean) + len(quarantine) + summary["duplicates_removed"]
    assert (report_dir / "quality_report.md").exists()
    assert (data_dir / "_ground_truth.json").exists()
