# Claims Data Cleanup & Report — Design

## Overview

A command-line data pipeline that **generates** a realistic but intentionally messy dataset
of 500 insurance claims, **cleans and validates** it, and produces a **data-quality report**.
It mirrors a real insurance operations workflow: claims arrive from multiple sources with
duplicates, inconsistent formatting, missing values, and typos, and must be standardized and
audited before any analysis can run.

The design separates **pure logic** (generation, cleaning, reporting — no I/O) from a thin
**CLI boundary** that reads and writes CSV. This keeps the error-prone parts (date parsing,
amount parsing, normalization) unit-testable, and makes the whole pipeline reproducible from a
seed.

## Goals / Non-goals

**Goals**
- Deterministic generation (fixed seed → identical dirty CSV, clean CSV, and report every run).
- Correct, explainable cleaning with every normalization decision documented.
- A report whose numbers **reconcile** and match the committed CSVs exactly.
- Tested core logic for the parsers and aggregations.

**Non-goals**
- No web UI, no deployment, no live data sources (CLI only — matches the brief's submission).
- No currency conversion between THB/VND (amounts are reported per-currency instead).

## Architecture

```
claims_cleanup/         # pure logic, no file I/O
  generate.py           # build records + inject issues; emit a ground-truth log
  clean.py              # parse/normalize/validate functions; dedup; quarantine
  report.py             # compute report statistics from before/after + detected issues
  cli.py                # argparse: generate | clean | report | verify | all  (the only I/O)
tests/                  # unit tests for the tricky pure functions
data/                   # committed outputs (dirty, clean, quarantine, ground-truth)
reports/                # committed quality_report.md
```

Data flow: `generate` → `data/claims_dirty.csv` (+ `data/_ground_truth.json`) →
`clean` → `data/claims_clean.csv` + `data/claims_quarantine.csv` (+ in-memory detected issues) →
`report` → `reports/quality_report.md`. `verify` cross-checks detected issues against the
ground-truth log. `all` runs the full chain.

## Data model (9 columns, per the brief)

| Column | Type | Generated distribution |
|---|---|---|
| `claim_id` | string `CLM-NNNNN` | unique sequence; some made missing/duplicated as issues |
| `policy_id` | string `POL-NNNNN` | random; some made missing |
| `member_name` | string | realistic names; casing varied as an issue |
| `claim_type` | enum | weighted toward OUTPATIENT; typos injected |
| `diagnosis` | string | ~15 realistic diagnoses; some emptied / "N/A" |
| `submitted_amount` | number | log-normal (most small, few large); negatives/zero/comma-strings injected |
| `currency` | string | mostly THB, some VND; case/name variants injected |
| `submitted_date` | string | spread across 2024; 3 formats injected |
| `status` | enum | APPROVED/REJECTED/PENDING/IN_REVIEW; out-of-enum variants injected |

## Generation

- Deterministic via `--seed` (default fixed). Produces exactly 500 rows.
- Injects at least one data-quality issue into **~15–20%** of rows, drawn from the brief's
  "issues to introduce" list (per column, see Data model). Some rows carry **multiple** issues.
- Writes a **ground-truth log** (`data/_ground_truth.json`): for each injected issue, the row
  index and issue type. This lets `verify` confirm the cleaner detected exactly what was injected.
- Writes the dirty CSV with the standard `csv` writer so comma-bearing values like `"15,000"`
  are correctly quoted (never hand-joined strings).

## Cleaning rules + decisions

The seven required operations, with the decisions made for each ambiguous case:

1. **Remove exact duplicate rows.** After trimming surrounding whitespace, byte-identical rows
   are removed and counted as `duplicates removed`. This runs **before** field normalization so
   the dedup result does not depend on normalization choices.
2. **Duplicate `claim_id` with differing data** is a real conflict — it is **flagged, not
   removed** (a human must resolve which record is correct).
3. **Normalize text + fix typos** via **explicit mapping tables** (not blind `.upper()`):
   - `member_name` → Title Case.
   - `claim_type` → `{outpatient, Outpateint, OP, … → OUTPATIENT}` etc.; unrecognized → flagged.
   - `status` → uppercased and validated against the enum; out-of-enum → flagged.
4. **Parse dates → ISO 8601 (YYYY-MM-DD).** Three input formats are accepted: `YYYY-MM-DD`,
   `DD/MM/YYYY`, and `Month D, YYYY`. **Slash dates are day-first** (`15/03/2024` = 15 March),
   parsed by trying explicit formats in order — never left to a library's locale guess.
   Impossible dates (e.g. `31/02/2024`) are flagged `invalid_date`.
5. **Invalid amounts (negative, zero)** are **flagged and quarantined** to
   `data/claims_quarantine.csv` with a `quarantine_reason` column — not silently deleted
   (claims data needs an audit trail). Quarantined rows are excluded from the clean CSV and
   from report statistics. Comma-strings like `"15,000"` are parsed to the number `15000`.
6. **Standardize currency** to uppercase ISO via mapping (`thb`/`Baht` → `THB`; `vnd` → `VND`);
   unrecognized → flagged. (No cross-currency conversion — see report.)
7. **Consistent null marker:** `"N/A"`, `"n/a"`, and empty strings become an **empty cell**
   (the canonical CSV null), applied uniformly across columns.

**Issue taxonomy** (detected and counted by type, aligned with what the generator injects):
`missing_claim_id`, `duplicate_claim_id`, `missing_policy_id`, `name_casing`,
`claim_type_typo`, `missing_diagnosis`, `invalid_amount`, `amount_comma_format`,
`currency_variant`, `date_format_variant`, `invalid_date`, `status_out_of_enum`,
`exact_duplicate_row`.

## Report (Markdown, `reports/quality_report.md`)

1. **Total rows before and after** cleaning.
2. **Duplicates removed.**
3. **Count of rows per issue type** (one row may contribute to several types), plus the count
   of distinct rows that had **at least one** issue (the ~15–20% figure).
4. **Summary statistics:** claims by type; claims by status; **average amount by type, reported
   per currency** (THB and VND are never averaged together — different denominations).
5. **Top 5 diagnoses** by frequency (casing-normalized; null/N/A excluded from the ranking).

**Reconciliation invariant** (asserted by the pipeline and shown in the report):
`rows_before = rows_after_clean + exact_duplicates_removed + quarantined_rows`.

## Self-verification

The `verify` command compares the cleaner's detected-issue set against the generator's
ground-truth log and reports detection coverage (every injected issue is found). The pipeline
also asserts the reconciliation invariant. Together these prove the report's numbers are
trustworthy rather than merely plausible.

## Testing

Unit tests (pytest) for the pure functions, covering the cases most likely to hide bugs:
- date parsing: each of the 3 formats, day-first correctness, invalid dates;
- amount parsing: comma-strings, negative, zero, non-numeric;
- mappings: claim_type typos, currency variants, status enum validation;
- dedup: exact duplicate vs. same-claim_id-different-data;
- top-5 diagnoses: casing normalization and null exclusion;
- the reconciliation invariant on a small synthetic set.

## Deliverables

- GitHub repository (its own repo).
- Committed `data/claims_dirty.csv`, `data/claims_clean.csv`, `data/claims_quarantine.csv`,
  `data/_ground_truth.json`, and `reports/quality_report.md`.
- `README.md`: what it is, how to run (`generate`/`clean`/`report`/`verify`/`all`), the cleaning
  decisions and assumptions, and the verification results.
- A timeline estimate.

## Tech stack

Python 3 **standard library only** (`csv`, `datetime`, `collections`, `random`, `dataclasses`).
For a 500-row dataset this is sufficient and dependency-light, and it keeps parsing and
normalization in explicit, tested functions rather than relying on a library's locale or
type auto-inference (which is exactly where silent data bugs hide). `argparse` CLI. `pytest`
for tests. No third-party runtime dependencies.
