"""Deterministic generator for a realistic but intentionally messy claims dataset.

Returns (rows, ground_truth). The ground-truth log records every injected issue as
{"row_index": int, "issue_type": str} so the cleaner's detection can be verified.
"""

import random

from claims_cleanup.constants import CLAIM_TYPES, STATUSES, DIAGNOSES

_FIRST = ["John", "Jane", "Somchai", "Mai", "Linh", "Wei", "Anan", "Nok", "Minh", "Ploy"]
_LAST = ["Doe", "Roe", "Tan", "Nguyen", "Lim", "Chen", "Pham", "Wong", "Tran", "Suk"]

# Issue kinds the generator can inject (covers every taxonomy type except the
# optional status_out_of_enum). The first len(_ISSUE_KINDS) targets get one of
# each, guaranteeing full coverage deterministically.
_ISSUE_KINDS = ["missing_claim_id", "duplicate_claim_id", "missing_policy_id", "name_casing",
                "claim_type_typo", "missing_diagnosis", "invalid_amount", "amount_comma_format",
                "currency_variant", "date_format_variant", "invalid_date", "exact_duplicate_row"]


def _clean_row(rng, i):
    """A single well-formed claim row (no issues)."""
    return {
        "claim_id": f"CLM-{i:05d}",
        "policy_id": f"POL-{rng.randint(100, 999)}",
        "member_name": f"{rng.choice(_FIRST)} {rng.choice(_LAST)}",
        "claim_type": rng.choices(CLAIM_TYPES, weights=[60, 20, 12, 8])[0],
        "diagnosis": rng.choice(DIAGNOSES),
        # log-normal -> most small, a few large (skewed, realistic)
        "submitted_amount": str(int(rng.lognormvariate(9.0, 1.0)) + 500),
        "currency": rng.choices(["THB", "VND"], weights=[80, 20])[0],
        "submitted_date": f"2024-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}",
        "status": rng.choices(STATUSES, weights=[55, 15, 20, 10])[0],
    }


def generate_dataset(seed, n=500):
    rng = random.Random(seed)
    rows = [_clean_row(rng, i + 1) for i in range(n)]
    gt = []

    n_issue = int(n * 0.17)
    targets = rng.sample(range(n), n_issue)
    # round-robin the first len(_ISSUE_KINDS) targets for guaranteed coverage,
    # then a random kind for the remainder
    kinds = [_ISSUE_KINDS[i] if i < len(_ISSUE_KINDS) else rng.choice(_ISSUE_KINDS)
             for i in range(n_issue)]

    def log(idx, issue_type):
        gt.append({"row_index": idx, "issue_type": issue_type})

    extra = []  # rows appended after the loop (exact dup / duplicate claim_id)
    for idx, kind in zip(targets, kinds):
        r = rows[idx]
        if kind == "missing_claim_id":
            r["claim_id"] = ""
        elif kind == "missing_policy_id":
            r["policy_id"] = ""
        elif kind == "name_casing":
            r["member_name"] = r["member_name"].upper()
        elif kind == "claim_type_typo":
            r["claim_type"] = rng.choice(["outpatient", "Outpateint", "OP", "ip"])
        elif kind == "missing_diagnosis":
            r["diagnosis"] = rng.choice(["", "N/A", "n/a"])
        elif kind == "invalid_amount":
            r["submitted_amount"] = rng.choice(["-100", "0"])
        elif kind == "amount_comma_format":
            val = max(int(r["submitted_amount"]), 1000)  # ensure a thousands separator exists
            r["submitted_amount"] = f"{val:,}"
        elif kind == "currency_variant":
            r["currency"] = rng.choice(["thb", "Baht", "vnd"])
        elif kind == "date_format_variant":
            y, m, d = r["submitted_date"].split("-")
            r["submitted_date"] = f"{d}/{m}/{y}"
        elif kind == "invalid_date":
            r["submitted_date"] = "31/02/2024"
        elif kind == "exact_duplicate_row":
            extra.append((dict(r), "exact_duplicate_row"))
            continue
        elif kind == "duplicate_claim_id":
            clone = _clean_row(rng, idx + 1)
            clone["claim_id"] = r["claim_id"]  # same id, different data
            extra.append((clone, "duplicate_claim_id"))
            continue
        log(idx, kind)

    for r, issue_type in extra:
        rows.append(r)
        log(len(rows) - 1, issue_type)

    return rows, gt
