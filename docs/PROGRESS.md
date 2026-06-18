# Project Progress

## Snapshot

- **Status:** complete. All 9 plan tasks done; **31 tests pass**; the pipeline runs
  end-to-end and `verify` reports `VERIFY OK` (all 12 injected issue types detected,
  reconciliation holds).
- **Deliverables (committed):** `data/claims_dirty.csv`, `data/claims_clean.csv`,
  `data/claims_quarantine.csv`, `data/_ground_truth.json`, `reports/quality_report.md`,
  `README.md`.
- **Latest run (seed 42):** 500 dirty rows → 484 clean + 6 quarantined + 10 exact
  duplicates removed.

## Decision Log

- Standard-library only (no pandas) — sufficient for 500 rows and keeps parsing in
  explicit, tested functions rather than relying on a library's locale/type inference.
- Dates parsed **day-first** to ISO 8601 via explicit formats; impossible dates flagged.
- Invalid amounts (negative/zero/unparseable) **quarantined with a reason**, not deleted
  (audit trail). Quarantine is reserved for amounts — the brief's only remove/flag case.
- An unparseable date is **flagged and the row kept** with a null date (a bad date is a
  missing value, not grounds to drop the whole claim).
- Exact-duplicate rows removed and counted; duplicate `claim_id` with different data is
  flagged and kept for human review.
- Null marker = empty cell, applied uniformly across columns.
- Average amount reported **per currency** — THB and VND are never averaged together.
- Generator emits a ground-truth log; `verify` cross-checks detection coverage and the
  reconciliation invariant, so the report's numbers are trustworthy, not just plausible.

## Session Log

- 2026-06-18: Built the pipeline task-by-task with TDD — constants, `parse_amount`,
  `parse_date`, field normalizers/mappings, `clean_dataset`, deterministic generator,
  report, and the CLI + self-verification — then generated the committed artifacts and
  wrote the docs. One commit per task; pushed to `github.com/CarsonDev1/claims-data-cleanup`.
