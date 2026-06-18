"""Command-line entry point — the only module that performs file I/O.

Subcommands: generate | clean | report | verify | all
"""

import argparse
import csv
import json
import sys
from pathlib import Path

from claims_cleanup.constants import COLUMNS
from claims_cleanup.generate import generate_dataset
from claims_cleanup.clean import clean_dataset
from claims_cleanup.report import build_report, render_markdown


def _write_csv(path, rows, columns):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        for r in rows:
            writer.writerow({c: ("" if r.get(c) is None else r.get(c)) for c in columns})


def _read_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _clean_from_disk(args):
    rows = _read_csv(Path(args.data_dir) / "claims_dirty.csv")
    return clean_dataset(rows)


def cmd_generate(args):
    rows, ground_truth = generate_dataset(args.seed)
    data_dir = Path(args.data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    _write_csv(data_dir / "claims_dirty.csv", rows, COLUMNS)
    (data_dir / "_ground_truth.json").write_text(json.dumps(ground_truth, indent=2), encoding="utf-8")


def cmd_clean(args):
    result = _clean_from_disk(args)
    data_dir = Path(args.data_dir)
    _write_csv(data_dir / "claims_clean.csv", result.clean_rows, COLUMNS)
    _write_csv(data_dir / "claims_quarantine.csv", result.quarantine_rows, COLUMNS + ["quarantine_reason"])
    rep = build_report(result)
    summary = {
        "rows_before": rep["rows_before"],
        "rows_after": rep["rows_after"],
        "duplicates_removed": rep["duplicates_removed"],
        "quarantined": rep["quarantined"],
    }
    (data_dir / "_report.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return result


def cmd_report(args):
    result = _clean_from_disk(args)
    report_dir = Path(args.report_dir)
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "quality_report.md").write_text(render_markdown(build_report(result)), encoding="utf-8")


def cmd_verify(args):
    data_dir = Path(args.data_dir)
    ground_truth = json.loads((data_dir / "_ground_truth.json").read_text(encoding="utf-8"))
    result = _clean_from_disk(args)
    truth_types = {g["issue_type"] for g in ground_truth}
    detected_types = {i.issue_type for i in result.detected_issues}
    missed = truth_types - detected_types
    reconciled = (
        result.rows_before
        == len(result.clean_rows) + result.duplicates_removed + len(result.quarantine_rows)
    )
    if missed or not reconciled:
        print(f"VERIFY FAILED: missed types={sorted(missed)} reconciliation_ok={reconciled}")
        sys.exit(1)
    print(f"VERIFY OK: all {len(truth_types)} injected issue types detected; reconciliation holds.")


def cmd_all(args):
    cmd_generate(args)
    cmd_clean(args)
    cmd_report(args)
    cmd_verify(args)


_COMMANDS = {
    "generate": cmd_generate,
    "clean": cmd_clean,
    "report": cmd_report,
    "verify": cmd_verify,
    "all": cmd_all,
}


def main(argv=None):
    parser = argparse.ArgumentParser(prog="claims_cleanup")
    parser.add_argument("command", choices=list(_COMMANDS))
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--report-dir", default="reports")
    args = parser.parse_args(argv)
    _COMMANDS[args.command](args)


if __name__ == "__main__":
    main()
