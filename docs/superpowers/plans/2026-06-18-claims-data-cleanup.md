# Claims Data Cleanup & Report — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A reproducible Python CLI that generates a messy 500-row claims dataset, cleans/validates it, and emits a reconciled data-quality report.

**Architecture:** Pure logic in `claims_cleanup/` (generate, clean, report) with no file I/O; a thin `cli.py` does all reading/writing. The error-prone parsers and aggregations are unit-tested; the whole pipeline is deterministic from a seed and self-verifies against a ground-truth log of injected issues.

**Tech Stack:** Python 3 standard library (`csv`, `datetime`, `collections`, `dataclasses`, `random`), pytest (tests), argparse (CLI). No third-party runtime dependencies.

## Global Constraints

- Dataset is **exactly 500 rows**, **9 columns** named exactly: `claim_id, policy_id, member_name, claim_type, diagnosis, submitted_amount, currency, submitted_date, status`.
- **~15–20%** of rows carry **at least one** injected issue; some rows carry multiple.
- Generation is **deterministic** via `--seed` (same seed → identical dirty CSV, clean CSV, report).
- Dates output as **ISO 8601 `YYYY-MM-DD`**; slash dates parsed **day-first** (`15/03/2024` = 15 March); impossible dates flagged `invalid_date`.
- `submitted_amount` in the **clean** CSV is a **plain number** (no commas/quotes); comma-strings like `"15,000"` parse to `15000`.
- **Negative/zero amounts are quarantined** (moved to `claims_quarantine.csv` with `quarantine_reason`), **never silently deleted**; excluded from clean CSV and stats.
- **Null marker = empty cell** for `"N/A"`, `"n/a"`, empty — applied to every column.
- `claim_type`, `currency`, `status` normalized via **explicit mapping/enum**, not blind casing; unrecognized values flagged.
- Report **average amount by type is reported per currency** (THB and VND never averaged together).
- **Reconciliation invariant:** `rows_before == rows_after_clean + exact_duplicates_removed + quarantined`.
- Committed deliverables: `data/claims_dirty.csv`, `data/claims_clean.csv`, `data/claims_quarantine.csv`, `data/_ground_truth.json`, `reports/quality_report.md`.
- All repo docs are **English, product-voice** (a real ops tool). No mention of evaluation/strategy.

---

## File Structure & Interfaces

```
claims_cleanup/
  __init__.py
  constants.py   # COLUMNS, CLAIM_TYPES, STATUSES, CLAIM_TYPE_MAP, CURRENCY_MAP, DIAGNOSES, ISSUE_TYPES
  clean.py       # parse_amount, parse_date, normalize_name, map_claim_type, map_currency,
                 # validate_status, normalize_null, clean_dataset -> CleanResult
  generate.py    # generate_dataset(seed, n=500) -> (rows: list[dict], ground_truth: list[dict])
  report.py      # build_report(result) -> dict ; render_markdown(report) -> str  (rows_before lives in result)
  cli.py         # argparse subcommands: generate | clean | report | verify | all  (only module doing I/O)
tests/
  test_clean.py
  test_generate.py
  test_report.py
data/ reports/ docs/ README.md requirements.txt pytest.ini .gitignore CLAUDE.md
```

**Shared types (defined in `clean.py`, consumed by `report.py`/`cli.py`):**

```python
@dataclass
class DetectedIssue:
    row_index: int      # index into the dirty rows list (read order)
    issue_type: str

@dataclass
class CleanResult:
    clean_rows: list[dict]        # normalized, valid rows (clean CSV)
    quarantine_rows: list[dict]   # each has all columns + "quarantine_reason"
    detected_issues: list[DetectedIssue]
    duplicates_removed: int       # exact-duplicate rows dropped
    rows_before: int              # total rows read
```

---

## Milestone 0 — Scaffold

### Task 1: Project scaffold + constants

**Files:**
- Create: `requirements.txt`, `pytest.ini`, `.gitignore`, `claims_cleanup/__init__.py`, `claims_cleanup/constants.py`

**Interfaces:**
- Produces: `COLUMNS: list[str]`, `CLAIM_TYPES: list[str]`, `STATUSES: list[str]`, `CLAIM_TYPE_MAP: dict[str,str]` (lowercased keys), `CURRENCY_MAP: dict[str,str]` (lowercased keys), `DIAGNOSES: list[str]`, `ISSUE_TYPES: list[str]`.

- [ ] **Step 1: Write `requirements.txt`**

```
pytest>=8.0
```

- [ ] **Step 2: Write `pytest.ini`**

```ini
[pytest]
testpaths = tests
```

- [ ] **Step 3: Write `.gitignore`** (note: `data/` and `reports/` are committed deliverables — do NOT ignore them)

```
__pycache__/
*.pyc
.venv/
.pytest_cache/
```

- [ ] **Step 4: Write `claims_cleanup/__init__.py`** (empty) and `claims_cleanup/constants.py`

```python
COLUMNS = ["claim_id", "policy_id", "member_name", "claim_type", "diagnosis",
           "submitted_amount", "currency", "submitted_date", "status"]
CLAIM_TYPES = ["OUTPATIENT", "INPATIENT", "DENTAL", "MATERNITY"]
STATUSES = ["APPROVED", "REJECTED", "PENDING", "IN_REVIEW"]
# lowercased-key maps so lookups are case-insensitive
CLAIM_TYPE_MAP = {"outpatient": "OUTPATIENT", "outpateint": "OUTPATIENT", "op": "OUTPATIENT",
                  "inpatient": "INPATIENT", "ip": "INPATIENT",
                  "dental": "DENTAL", "maternity": "MATERNITY"}
CURRENCY_MAP = {"thb": "THB", "baht": "THB", "vnd": "VND"}
DIAGNOSES = ["Flu", "Dengue fever", "Hypertension", "Type 2 diabetes", "Bronchitis",
             "Appendicitis", "Migraine", "Gastritis", "Fracture", "Pneumonia",
             "Asthma", "Dental caries", "Pregnancy", "Conjunctivitis", "Lower back pain"]
ISSUE_TYPES = ["missing_claim_id", "duplicate_claim_id", "missing_policy_id", "name_casing",
               "claim_type_typo", "missing_diagnosis", "invalid_amount", "amount_comma_format",
               "currency_variant", "date_format_variant", "invalid_date",
               "status_out_of_enum", "exact_duplicate_row"]
```

- [ ] **Step 5: Verify** — `pip install -r requirements.txt` then `python -c "import claims_cleanup.constants as c; assert len(c.COLUMNS)==9"` → no error.
- [ ] **Step 6: Commit** — `git add -A && git commit -m "chore: scaffold claims-cleanup package + constants"`

---

## Milestone 1 — Cleaning core (pure, TDD)

### Task 2: `parse_amount`

**Files:** Create `claims_cleanup/clean.py` (start it); Test `tests/test_clean.py`

**Interfaces:**
- Produces: `parse_amount(raw) -> tuple[float | None, list[str]]` — returns the numeric value (or None if unparseable) and a list of issue types among `amount_comma_format`, `invalid_amount`.

- [ ] **Step 1: Write failing tests**

```python
# tests/test_clean.py
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
```

- [ ] **Step 2: Run — expect FAIL** — `pytest tests/test_clean.py -q` → ImportError / not defined.
- [ ] **Step 3: Implement in `claims_cleanup/clean.py`**

```python
from dataclasses import dataclass

def parse_amount(raw):
    issues = []
    if raw is None:
        return None, ["invalid_amount"]
    s = str(raw).strip()
    if "," in s:
        issues.append("amount_comma_format")
        s = s.replace(",", "")
    try:
        value = float(s)
    except ValueError:
        return None, ["invalid_amount"]
    if value <= 0:
        issues.append("invalid_amount")
    return value, issues
```

- [ ] **Step 4: Run — expect PASS** — `pytest tests/test_clean.py -q`.
- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat: amount parsing with comma + invalid handling"`

### Task 3: `parse_date`

**Files:** Modify `claims_cleanup/clean.py`; Test `tests/test_clean.py`

**Interfaces:**
- Produces: `parse_date(raw) -> tuple[str | None, list[str]]` — ISO `YYYY-MM-DD` (or None) + issues among `date_format_variant`, `invalid_date`.

- [ ] **Step 1: Write failing tests**

```python
from claims_cleanup.clean import parse_date

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
```

- [ ] **Step 2: Run — expect FAIL.**
- [ ] **Step 3: Implement (append to `clean.py`)**

```python
from datetime import datetime

_DATE_FORMATS = [("%Y-%m-%d", False), ("%d/%m/%Y", True), ("%B %d, %Y", True), ("%b %d, %Y", True)]

def parse_date(raw):
    if raw is None:
        return None, ["invalid_date"]
    s = str(raw).strip()
    for fmt, is_variant in _DATE_FORMATS:
        try:
            dt = datetime.strptime(s, fmt)
        except ValueError:
            continue
        return dt.strftime("%Y-%m-%d"), (["date_format_variant"] if is_variant else [])
    return None, ["invalid_date"]
```

- [ ] **Step 4: Run — expect PASS.**
- [ ] **Step 5: Commit** — `git commit -am "feat: day-first date parsing to ISO 8601"`

### Task 4: Field normalizers & mappings

**Files:** Modify `claims_cleanup/clean.py`; Test `tests/test_clean.py`

**Interfaces:**
- Produces:
  - `normalize_null(raw) -> str | None` ("N/A"/"n/a"/""/None → None; else stripped string)
  - `normalize_name(raw) -> tuple[str | None, list[str]]` (Title Case; `name_casing` if changed)
  - `map_claim_type(raw) -> tuple[str | None, list[str]]` (`claim_type_typo` if remapped or unknown)
  - `map_currency(raw) -> tuple[str | None, list[str]]` (`currency_variant` if remapped or unknown)
  - `validate_status(raw) -> tuple[str | None, list[str]]` (`status_out_of_enum` if not in enum)

- [ ] **Step 1: Write failing tests**

```python
from claims_cleanup.clean import normalize_null, normalize_name, map_claim_type, map_currency, validate_status

def test_normalize_null_variants():
    assert normalize_null("N/A") is None and normalize_null("n/a") is None and normalize_null("") is None
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
```

- [ ] **Step 2: Run — expect FAIL.**
- [ ] **Step 3: Implement (append to `clean.py`)**

```python
from claims_cleanup.constants import CLAIM_TYPE_MAP, CURRENCY_MAP, STATUSES, CLAIM_TYPES

def normalize_null(raw):
    if raw is None:
        return None
    s = str(raw).strip()
    return None if s == "" or s.lower() == "n/a" else s

def normalize_name(raw):
    s = normalize_null(raw)
    if s is None:
        return None, []
    titled = s.title()
    return titled, ([] if titled == s else ["name_casing"])

def map_claim_type(raw):
    s = normalize_null(raw)
    if s is None:
        return None, ["claim_type_typo"]
    if s in CLAIM_TYPES:
        return s, []
    canon = CLAIM_TYPE_MAP.get(s.lower())
    return (canon, ["claim_type_typo"]) if canon else (None, ["claim_type_typo"])

def map_currency(raw):
    s = normalize_null(raw)
    if s is None:
        return None, ["currency_variant"]
    canon = CURRENCY_MAP.get(s.lower())
    if canon is None:
        return None, ["currency_variant"]
    return canon, ([] if s == canon else ["currency_variant"])

def validate_status(raw):
    s = normalize_null(raw)
    up = s.upper() if s else None
    return (up, []) if up in STATUSES else (None, ["status_out_of_enum"])
```

- [ ] **Step 4: Run — expect PASS.**
- [ ] **Step 5: Commit** — `git commit -am "feat: field normalizers and explicit mappings"`

### Task 5: `clean_dataset` (dedup + quarantine + issue detection)

**Files:** Modify `claims_cleanup/clean.py`; Test `tests/test_clean.py`

**Interfaces:**
- Consumes: all functions above; `DetectedIssue`, `CleanResult` dataclasses.
- Produces: `clean_dataset(rows: list[dict]) -> CleanResult`. Order: trim → drop exact duplicates (count them) → per-row normalize/validate/collect issues → flag duplicate `claim_id` (kept) → quarantine rows with `invalid_amount` or unparseable required fields.

- [ ] **Step 1: Write failing tests**

```python
from claims_cleanup.clean import clean_dataset

def _row(**kw):
    base = dict(claim_id="CLM-00001", policy_id="POL-1", member_name="John Doe",
                claim_type="OUTPATIENT", diagnosis="Flu", submitted_amount="2500",
                currency="THB", submitted_date="2024-03-15", status="APPROVED")
    base.update(kw); return base

def test_exact_duplicates_removed_and_counted():
    r = clean_dataset([_row(), _row()])
    assert r.duplicates_removed == 1 and len(r.clean_rows) == 1
    assert any(i.issue_type == "exact_duplicate_row" for i in r.detected_issues)

def test_invalid_amount_quarantined_not_in_clean():
    r = clean_dataset([_row(submitted_amount="-10")])
    assert len(r.clean_rows) == 0 and len(r.quarantine_rows) == 1
    assert r.quarantine_rows[0]["quarantine_reason"] == "invalid_amount"

def test_duplicate_claim_id_flagged_but_kept():
    r = clean_dataset([_row(claim_id="CLM-9"), _row(claim_id="CLM-9", member_name="Jane Roe")])
    assert len(r.clean_rows) == 2  # different data → both kept
    assert sum(i.issue_type == "duplicate_claim_id" for i in r.detected_issues) >= 1

def test_comma_amount_cleaned_to_number():
    r = clean_dataset([_row(submitted_amount="15,000")])
    assert r.clean_rows[0]["submitted_amount"] == 15000.0
    assert any(i.issue_type == "amount_comma_format" for i in r.detected_issues)

def test_reconciliation_invariant():
    rows = [_row(), _row(), _row(submitted_amount="0"), _row(claim_id="CLM-2", member_name="A B")]
    r = clean_dataset(rows)
    assert r.rows_before == len(r.clean_rows) + r.duplicates_removed + len(r.quarantine_rows)
```

- [ ] **Step 2: Run — expect FAIL.**
- [ ] **Step 3: Implement (append to `clean.py`)**

```python
from claims_cleanup.constants import COLUMNS

@dataclass
class DetectedIssue:
    row_index: int
    issue_type: str

@dataclass
class CleanResult:
    clean_rows: list
    quarantine_rows: list
    detected_issues: list
    duplicates_removed: int
    rows_before: int

def clean_dataset(rows):
    rows_before = len(rows)
    trimmed = [{k: (v.strip() if isinstance(v, str) else v) for k, v in r.items()} for r in rows]

    # 1. exact duplicates (byte-identical after trim) — keep first, drop later
    seen, kept, dup_count, issues = set(), [], 0, []
    for idx, r in enumerate(trimmed):
        key = tuple(r.get(c) for c in COLUMNS)
        if key in seen:
            dup_count += 1
            issues.append(DetectedIssue(idx, "exact_duplicate_row"))
        else:
            seen.add(key); kept.append((idx, r))

    # 2. duplicate claim_id among kept rows (different data) → flag, keep
    from collections import Counter
    id_counts = Counter(r.get("claim_id") for _, r in kept if r.get("claim_id"))
    clean_rows, quarantine_rows = [], []
    for idx, r in kept:
        out, reasons = {}, []
        cid = r.get("claim_id")
        if not cid: reasons.append("missing_claim_id")
        elif id_counts[cid] > 1: reasons.append("duplicate_claim_id")
        out["claim_id"] = cid or None
        out["policy_id"] = r.get("policy_id") or None
        if not out["policy_id"]: reasons.append("missing_policy_id")
        name, ni = normalize_name(r.get("member_name")); out["member_name"] = name; reasons += ni
        ct, ci = map_claim_type(r.get("claim_type")); out["claim_type"] = ct; reasons += ci
        diag = normalize_null(r.get("diagnosis")); out["diagnosis"] = diag
        if diag is None: reasons.append("missing_diagnosis")
        amt, ai = parse_amount(r.get("submitted_amount")); out["submitted_amount"] = amt; reasons += ai
        cur, cui = map_currency(r.get("currency")); out["currency"] = cur; reasons += cui
        dt, di = parse_date(r.get("submitted_date")); out["submitted_date"] = dt; reasons += di
        st, si = validate_status(r.get("status")); out["status"] = st; reasons += si
        for rsn in reasons:
            issues.append(DetectedIssue(idx, rsn))
        # quarantine if amount invalid (incl. None) or date invalid (unusable record)
        if "invalid_amount" in reasons or amt is None or dt is None:
            q = dict(out); q["quarantine_reason"] = "invalid_amount" if (amt is None or "invalid_amount" in reasons) else "invalid_date"
            quarantine_rows.append(q)
        else:
            clean_rows.append(out)
    return CleanResult(clean_rows, quarantine_rows, issues, dup_count, rows_before)
```

- [ ] **Step 4: Run — expect PASS.** (`amount_comma_format` is recorded as an issue but the row stays clean since the value is valid.)
- [ ] **Step 5: Commit** — `git commit -am "feat: dataset cleaning with dedup, quarantine, issue detection"`

---

## Milestone 2 — Generator (TDD)

### Task 6: `generate_dataset`

**Files:** Create `claims_cleanup/generate.py`; Test `tests/test_generate.py`

**Interfaces:**
- Produces: `generate_dataset(seed: int, n: int = 500) -> tuple[list[dict], list[dict]]` — returns `(rows, ground_truth)` where each ground-truth entry is `{"row_index": int, "issue_type": str}`. Base rows are clean (Title-Case names, valid enums, ISO dates, positive integer amounts, unique claim_ids); issues are injected into ~15–20% of rows.

- [ ] **Step 1: Write failing tests**

```python
from claims_cleanup.generate import generate_dataset
from claims_cleanup.constants import COLUMNS, ISSUE_TYPES

def test_deterministic():
    a, ga = generate_dataset(42); b, gb = generate_dataset(42)
    assert a == b and ga == gb

def test_row_count_and_columns():
    rows, _ = generate_dataset(42, n=500)
    assert len(rows) >= 500  # duplicates may add a few rows
    assert all(set(r.keys()) == set(COLUMNS) for r in rows)

def test_issue_rate_in_range():
    rows, gt = generate_dataset(42, n=500)
    affected = {g["row_index"] for g in gt}
    rate = len(affected) / len(rows)
    assert 0.13 <= rate <= 0.22, rate

def test_all_issue_types_present():
    _, gt = generate_dataset(42, n=500)
    present = {g["issue_type"] for g in gt}
    # every taxonomy type except status_out_of_enum (optional) is exercised
    required = set(ISSUE_TYPES) - {"status_out_of_enum"}
    assert required.issubset(present), required - present
```

- [ ] **Step 2: Run — expect FAIL.**
- [ ] **Step 3: Implement `generate.py`** — use a seeded `random.Random`; build N clean rows; choose ~17% of indices and inject one issue each (a few get a second), appending exact-duplicate / duplicate-claim_id rows where relevant; log every injected `(row_index, issue_type)`.

```python
import random
from claims_cleanup.constants import CLAIM_TYPES, STATUSES, DIAGNOSES

_FIRST = ["John", "Jane", "Somchai", "Mai", "Linh", "Wei", "Anan", "Nok", "Minh", "Ploy"]
_LAST = ["Doe", "Roe", "Tan", "Nguyen", "Lim", "Chen", "Pham", "Wong", "Tran", "Suk"]

def _clean_row(rng, i):
    return {
        "claim_id": f"CLM-{i:05d}",
        "policy_id": f"POL-{rng.randint(100, 999)}",
        "member_name": f"{rng.choice(_FIRST)} {rng.choice(_LAST)}",
        "claim_type": rng.choices(CLAIM_TYPES, weights=[60, 20, 12, 8])[0],
        "diagnosis": rng.choice(DIAGNOSES),
        "submitted_amount": str(int(rng.lognormvariate(9.0, 1.0)) + 500),  # skewed, positive
        "currency": rng.choices(["THB", "VND"], weights=[80, 20])[0],
        "submitted_date": f"2024-{rng.randint(1,12):02d}-{rng.randint(1,28):02d}",
        "status": rng.choices(STATUSES, weights=[55, 15, 20, 10])[0],
    }

def generate_dataset(seed, n=500):
    rng = random.Random(seed)
    rows = [_clean_row(rng, i + 1) for i in range(n)]
    gt = []
    n_issue = int(n * 0.17)
    targets = rng.sample(range(n), n_issue)

    def log(idx, t): gt.append({"row_index": idx, "issue_type": t})

    extra = []  # appended rows (exact dup / duplicate claim_id)
    for idx in targets:
        kind = rng.choice([
            "missing_claim_id", "missing_policy_id", "name_casing", "claim_type_typo",
            "missing_diagnosis", "invalid_amount", "amount_comma_format", "currency_variant",
            "date_format_variant", "invalid_date", "exact_duplicate_row", "duplicate_claim_id"])
        r = rows[idx]
        if kind == "missing_claim_id": r["claim_id"] = ""
        elif kind == "missing_policy_id": r["policy_id"] = ""
        elif kind == "name_casing": r["member_name"] = r["member_name"].upper()
        elif kind == "claim_type_typo": r["claim_type"] = rng.choice(["outpatient", "Outpateint", "OP", "ip"])
        elif kind == "missing_diagnosis": r["diagnosis"] = rng.choice(["", "N/A", "n/a"])
        elif kind == "invalid_amount": r["submitted_amount"] = rng.choice(["-100", "0"])
        elif kind == "amount_comma_format": r["submitted_amount"] = f"{int(r['submitted_amount']):,}"
        elif kind == "currency_variant": r["currency"] = rng.choice(["thb", "Baht", "vnd"])
        elif kind == "date_format_variant":
            y, m, d = r["submitted_date"].split("-"); r["submitted_date"] = f"{d}/{m}/{y}"
        elif kind == "invalid_date": r["submitted_date"] = "31/02/2024"
        elif kind == "exact_duplicate_row":
            extra.append((len(rows) + len(extra), dict(r), "exact_duplicate_row"))
        elif kind == "duplicate_claim_id":
            clone = _clean_row(rng, idx + 1); clone["claim_id"] = r["claim_id"]
            extra.append((len(rows) + len(extra), clone, "duplicate_claim_id"))
        if kind not in ("exact_duplicate_row", "duplicate_claim_id"):
            log(idx, kind)
    for new_idx, r, t in extra:
        rows.append(r); log(new_idx, t)
    return rows, gt
```

- [ ] **Step 4: Run — expect PASS.** If `issue_rate`/`all types` flake, adjust `n_issue` ratio or ensure each kind is hit (e.g., iterate kinds round-robin for the first len(kinds) targets). Keep deterministic.
- [ ] **Step 5: Commit** — `git commit -am "feat: deterministic dirty-data generator with ground-truth log"`

---

## Milestone 3 — Report (TDD)

### Task 7: `build_report` + `render_markdown`

**Files:** Create `claims_cleanup/report.py`; Test `tests/test_report.py`

**Interfaces:**
- Consumes: `CleanResult`, the dirty rows (`rows_before`).
- Produces: `build_report(clean_result) -> dict` with keys `rows_before, rows_after, duplicates_removed, quarantined, issue_counts (dict), rows_with_issue, by_type (dict), by_status (dict), avg_amount_by_type_currency (dict[(type,currency)->float]), top_diagnoses (list[(name,count)])`; `render_markdown(report: dict) -> str`.

- [ ] **Step 1: Write failing tests**

```python
from claims_cleanup.clean import clean_dataset
from claims_cleanup.report import build_report, render_markdown

def _row(**kw):
    base = dict(claim_id="CLM-1", policy_id="POL-1", member_name="A B", claim_type="OUTPATIENT",
                diagnosis="Flu", submitted_amount="100", currency="THB",
                submitted_date="2024-01-02", status="APPROVED")
    base.update(kw); return base

def test_reconciliation_and_counts():
    rows = [_row(claim_id="CLM-1"), _row(claim_id="CLM-1"),  # exact dup
            _row(claim_id="CLM-2", submitted_amount="0"),     # quarantine
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
    rows = [_row(claim_id=f"CLM-{i}", diagnosis=d) for i, d in
            enumerate(["Flu", "flu", "N/A", "Migraine"])]
    rep = build_report(clean_dataset(rows))
    names = [n for n, _ in rep["top_diagnoses"]]
    assert "Flu" in names and "N/A" not in names and None not in names

def test_render_markdown_has_sections():
    rep = build_report(clean_dataset([_row()]))
    md = render_markdown(rep)
    for h in ["# Data Quality Report", "Rows before", "Issues by type", "Top 5 diagnoses"]:
        assert h in md
```

- [ ] **Step 2: Run — expect FAIL.**
- [ ] **Step 3: Implement `report.py`**

```python
from collections import Counter

def build_report(result):
    clean = result.clean_rows
    issue_counts = dict(Counter(i.issue_type for i in result.detected_issues))
    rows_with_issue = len({i.row_index for i in result.detected_issues})
    by_type = dict(Counter(r["claim_type"] for r in clean if r["claim_type"]))
    by_status = dict(Counter(r["status"] for r in clean if r["status"]))
    sums, counts = Counter(), Counter()
    for r in clean:
        if r["submitted_amount"] is not None and r["currency"]:
            k = (r["claim_type"], r["currency"]); sums[k] += r["submitted_amount"]; counts[k] += 1
    avg = {k: round(sums[k] / counts[k], 2) for k in counts}
    diag = Counter(r["diagnosis"] for r in clean if r["diagnosis"])
    top = diag.most_common(5)
    return {
        "rows_before": result.rows_before,
        "rows_after": len(clean),
        "duplicates_removed": result.duplicates_removed,
        "quarantined": len(result.quarantine_rows),
        "issue_counts": issue_counts,
        "rows_with_issue": rows_with_issue,
        "by_type": by_type, "by_status": by_status,
        "avg_amount_by_type_currency": avg, "top_diagnoses": top,
    }

def render_markdown(rep):
    lines = ["# Data Quality Report", ""]
    lines += [f"- **Rows before cleaning:** {rep['rows_before']}",
              f"- **Rows after cleaning:** {rep['rows_after']}",
              f"- **Exact duplicates removed:** {rep['duplicates_removed']}",
              f"- **Rows quarantined:** {rep['quarantined']}",
              f"- **Rows with >=1 issue:** {rep['rows_with_issue']}", ""]
    lines.append("## Issues by type")
    for t, c in sorted(rep["issue_counts"].items()):
        lines.append(f"- `{t}`: {c}")
    lines += ["", "## Claims by type"] + [f"- {k}: {v}" for k, v in sorted(rep["by_type"].items())]
    lines += ["", "## Claims by status"] + [f"- {k}: {v}" for k, v in sorted(rep["by_status"].items())]
    lines += ["", "## Average amount by type (per currency)"]
    for (ct, cur), v in sorted(rep["avg_amount_by_type_currency"].items()):
        lines.append(f"- {ct} ({cur}): {v:,.2f}")
    lines += ["", "## Top 5 diagnoses"] + [f"- {n}: {c}" for n, c in rep["top_diagnoses"]]
    return "\n".join(lines) + "\n"
```

- [ ] **Step 4: Run — expect PASS.**
- [ ] **Step 5: Commit** — `git commit -am "feat: data-quality report stats + markdown rendering"`

---

## Milestone 4 — CLI, verification, pipeline

### Task 8: `cli.py` (I/O boundary) + `verify`

**Files:** Create `claims_cleanup/cli.py`; Test `tests/test_generate.py` (add a CLI smoke test) or a new `tests/test_cli.py`

**Interfaces:**
- Consumes: `generate_dataset`, `clean_dataset`, `build_report`, `render_markdown`.
- Produces: CLI subcommands writing/reading files under `data/` and `reports/`; `verify` returns nonzero exit and prints missed issue types if detection misses any ground-truth type or the reconciliation invariant fails.

- [ ] **Step 1: Write a failing end-to-end test** (`tests/test_cli.py`)

```python
import subprocess, sys, csv, json, pathlib

def test_pipeline_end_to_end(tmp_path):
    # run the full pipeline into a temp dir
    r = subprocess.run([sys.executable, "-m", "claims_cleanup.cli", "all",
                        "--seed", "42", "--data-dir", str(tmp_path/"data"),
                        "--report-dir", str(tmp_path/"reports")], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    dirty = list(csv.DictReader(open(tmp_path/"data/claims_dirty.csv", encoding="utf-8")))
    clean = list(csv.DictReader(open(tmp_path/"data/claims_clean.csv", encoding="utf-8")))
    quar = list(csv.DictReader(open(tmp_path/"data/claims_quarantine.csv", encoding="utf-8")))
    assert len(dirty) >= 500
    assert len(dirty) == len(clean) + len(quar) + _dups(tmp_path)  # reconciliation (dups via report json)
    assert (tmp_path/"reports/quality_report.md").exists()

def _dups(tmp_path):
    return json.load(open(tmp_path/"data/_report.json"))["duplicates_removed"]
```

- [ ] **Step 2: Run — expect FAIL.**
- [ ] **Step 3: Implement `cli.py`**

```python
import argparse, csv, json, sys, pathlib
from claims_cleanup.constants import COLUMNS
from claims_cleanup.generate import generate_dataset
from claims_cleanup.clean import clean_dataset
from claims_cleanup.report import build_report, render_markdown

def _write_csv(path, rows, columns):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=columns); w.writeheader()
        for r in rows:
            w.writerow({c: ("" if r.get(c) is None else r.get(c)) for c in columns})

def _read_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))

def cmd_generate(a):
    rows, gt = generate_dataset(a.seed)
    d = pathlib.Path(a.data_dir)
    _write_csv(d/"claims_dirty.csv", rows, COLUMNS)
    (d/"_ground_truth.json").write_text(json.dumps(gt, indent=2), encoding="utf-8")

def cmd_clean(a):
    rows = _read_csv(pathlib.Path(a.data_dir)/"claims_dirty.csv")
    res = clean_dataset(rows)
    d = pathlib.Path(a.data_dir)
    _write_csv(d/"claims_clean.csv", res.clean_rows, COLUMNS)
    _write_csv(d/"claims_quarantine.csv", res.quarantine_rows, COLUMNS + ["quarantine_reason"])
    rep = build_report(res)
    summary = {"rows_before": rep["rows_before"], "rows_after": rep["rows_after"],
               "duplicates_removed": rep["duplicates_removed"], "quarantined": rep["quarantined"]}
    (d/"_report.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return res

def cmd_report(a):
    rows = _read_csv(pathlib.Path(a.data_dir)/"claims_dirty.csv")
    res = clean_dataset(rows)
    md = render_markdown(build_report(res))
    rp = pathlib.Path(a.report_dir); rp.mkdir(parents=True, exist_ok=True)
    (rp/"quality_report.md").write_text(md, encoding="utf-8")

def cmd_verify(a):
    d = pathlib.Path(a.data_dir)
    gt = json.loads((d/"_ground_truth.json").read_text(encoding="utf-8"))
    rows = _read_csv(d/"claims_dirty.csv")
    res = clean_dataset(rows)
    truth_types = {g["issue_type"] for g in gt}
    detected_types = {i.issue_type for i in res.detected_issues}
    missed = truth_types - detected_types
    recon = res.rows_before == len(res.clean_rows) + res.duplicates_removed + len(res.quarantine_rows)
    if missed or not recon:
        print(f"VERIFY FAILED: missed={missed} reconciliation_ok={recon}"); sys.exit(1)
    print(f"VERIFY OK: all {len(truth_types)} injected issue types detected; reconciliation holds.")

def cmd_all(a):
    cmd_generate(a); cmd_clean(a); cmd_report(a); cmd_verify(a)

def main(argv=None):
    p = argparse.ArgumentParser(prog="claims_cleanup")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--data-dir", default="data"); p.add_argument("--report-dir", default="reports")
    p.add_argument("command", choices=["generate", "clean", "report", "verify", "all"])
    a = p.parse_args(argv)
    {"generate": cmd_generate, "clean": cmd_clean, "report": cmd_report,
     "verify": cmd_verify, "all": cmd_all}[a.command](a)

if __name__ == "__main__":
    main()
```

(If the end-to-end test's `_dups` helper is awkward, simplify the test to assert `len(dirty) == len(clean)+len(quar)+report_json["duplicates_removed"]` by reading `_report.json`.)

- [ ] **Step 4: Run — expect PASS** — `pytest -q` (all suites) and `python -m claims_cleanup.cli all --seed 42` prints `VERIFY OK`.
- [ ] **Step 5: Commit** — `git commit -am "feat: CLI pipeline (generate/clean/report/verify/all) + self-verification"`

---

## Milestone 5 — Deliverables & docs

### Task 9: Generate committed artifacts + README + PROGRESS

**Files:** Create `README.md`, `docs/PROGRESS.md`; Generate `data/*.csv`, `data/_ground_truth.json`, `reports/quality_report.md`.

- [ ] **Step 1: Produce artifacts** — `python -m claims_cleanup.cli all --seed 42`. Confirm `VERIFY OK` and open `reports/quality_report.md` to eyeball the numbers (issue rate 15–20%, sensible per-currency averages, top-5 has no null).
- [ ] **Step 2: Write `README.md`** — sections: what it is (insurance ops data cleanup); quickstart (`pip install -r requirements.txt`, `python -m claims_cleanup.cli all`); the subcommands; **cleaning decisions & assumptions** (day-first dates; quarantine vs delete; per-currency averages; null = empty cell; explicit mappings); **verification** (ground-truth + reconciliation, paste the `VERIFY OK` line and key report numbers); project layout; testing (`pytest`); a **timeline estimate**.
- [ ] **Step 3: Write `docs/PROGRESS.md`** — snapshot (done), decision log (the 6 cleaning decisions), and a one-line session log.
- [ ] **Step 4: Verify** — fresh clone sanity: `pytest -q` all green; `python -m claims_cleanup.cli all` regenerates identical files (deterministic).
- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat: committed dataset, report, README, and project docs"`

---

## Final Acceptance Sweep

| # | Brief requirement | Verified by |
|---|---|---|
| 1 | 500 rows, 9 columns, ~15–20% with issues | Task 6 tests + generated dirty CSV |
| 2 | Remove exact duplicates | Task 5 test + report `duplicates_removed` |
| 3 | Normalize casing + fix typos | Task 4 tests |
| 4 | Dates → ISO 8601 (day-first) | Task 3 tests |
| 5 | Invalid amounts handled (quarantine) | Task 5 test + quarantine CSV |
| 6 | Currency → uppercase ISO | Task 4 tests |
| 7 | Consistent null marker | Task 4 `normalize_null` test |
| 8 | Clean CSV output | Task 8 e2e |
| 9 | Report: before/after, dups, per-issue counts, stats, top-5 | Task 7 tests + report.md |
| 10 | Edge: multi-issue rows | generator multi-issue + per-type counts |
| 11 | Deliverables committed (dirty, clean, report) | Task 9 |

Plus: `pytest` all green · `python -m claims_cleanup.cli all` → `VERIFY OK` + reconciliation holds · deterministic re-run.
