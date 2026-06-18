# Claims Data Cleanup & Report

A small, dependency-light Python pipeline that takes a messy export of insurance claims,
cleans and validates it, and produces a data-quality report. It mirrors a real
insurance-operations workflow: claims arrive from many sources with duplicates,
inconsistent formatting, missing values, and typos, and must be standardized and audited
before any analysis can run.

The pipeline is **reproducible** (everything is generated from a fixed seed) and
**self-verifying** (the cleaner's issue detection is checked against a ground-truth log of
what was injected, and the row counts must reconcile).

## Project layout

- `claims_cleanup/` — pure logic, no file I/O: `generate`, `clean`, `report`
- `claims_cleanup/cli.py` — command-line entry point (the only module that reads/writes files)
- `data/` — generated artifacts: dirty CSV, clean CSV, quarantine CSV, ground-truth log
- `reports/quality_report.md` — the data-quality report
- `tests/` — unit tests for the parsers/aggregations + an end-to-end CLI test
- `docs/` — design spec, implementation plan, and progress notes

## Quickstart

```bash
python -m venv .venv
source .venv/Scripts/activate      # Windows (Git Bash); use .venv/bin/activate on macOS/Linux
pip install -r requirements.txt

python -m claims_cleanup.cli all   # generate -> clean -> report -> verify
pytest                             # run the test suite
```

Subcommands (each accepts `--seed`, `--data-dir`, `--report-dir`):

| Command | Writes |
|---|---|
| `generate` | `data/claims_dirty.csv` + `data/_ground_truth.json` |
| `clean` | `data/claims_clean.csv` + `data/claims_quarantine.csv` |
| `report` | `reports/quality_report.md` |
| `verify` | nothing — exits non-zero if detection or reconciliation fails |
| `all` | runs all of the above |

## The dataset

`generate` produces 500 well-formed claims with realistic skew (most OUTPATIENT, log-normal
amounts, mostly THB with some VND), then injects data-quality issues into ~15–20% of rows:
missing/duplicate ids, inconsistent name casing, claim-type typos, empty/"N/A" diagnoses,
negative/zero/comma-formatted amounts, currency variants, mixed date formats, impossible
dates, and exact-duplicate rows. Every injection is recorded in `data/_ground_truth.json`.

## Cleaning decisions

- **Dates → ISO 8601 (`YYYY-MM-DD`).** Slash dates are read **day-first** (`15/03/2024` =
  15 March), by trying explicit formats in order — never left to a locale guess. Impossible
  dates (e.g. `31/02/2024`) are flagged `invalid_date` and the row is **kept** with an empty
  date (the brief only removes rows for invalid amounts, so a bad date is treated as a
  missing value, not a reason to drop the claim).
- **Invalid amounts (negative/zero) are quarantined, not deleted.** Claims data needs an
  audit trail, so such rows move to `claims_quarantine.csv` with a `quarantine_reason` and
  are excluded from the clean output and the statistics. Comma strings like `"15,000"` parse
  to `15000`.
- **Exact-duplicate rows are removed and counted;** a duplicate `claim_id` with *different*
  data is a genuine conflict, so it is flagged and kept for a human to resolve.
- **Null marker = empty cell** for `"N/A"`, `"n/a"`, and blanks, applied uniformly.
- **`claim_type`, `currency`, `status` are normalized via explicit mapping/enum tables**
  (`Outpateint`/`OP` → `OUTPATIENT`, `Baht` → `THB`, …), not blind casing.
- **Average amount is reported per currency.** THB and VND are different denominations and
  are never averaged together.

## Verification

`python -m claims_cleanup.cli verify` checks:

1. **Detection coverage** — every issue type in the ground-truth log is found by the cleaner.
2. **Reconciliation** — `rows_before == rows_after_clean + exact_duplicates_removed + quarantined`.

Latest run (seed 42): `VERIFY OK: all 12 injected issue types detected; reconciliation holds.`
500 dirty rows → 484 clean + 6 quarantined + 10 exact duplicates removed. See
[`reports/quality_report.md`](reports/quality_report.md) for the full breakdown.

## Testing

```bash
pytest    # 31 tests: parsers, mappings, dedup/quarantine, generator, report, end-to-end CLI
```

## Notes & assumptions

- Standard library only — no third-party runtime dependencies.
- The dataset is synthetic and self-generated; amounts are expressed in each row's own
  currency unit (no cross-currency conversion is performed).
- `submitted_date` is the only date column; values fall in 2024.

## Timeline

Estimated **~3–5 hours**: generator + ground-truth log (~1h), cleaning functions and
dataset logic with tests (~1.5h), report + CLI + verification (~1h), artifacts and docs
(~0.5h). Built incrementally, test-first, one concern per commit.
