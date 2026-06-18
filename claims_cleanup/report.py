"""Build the data-quality report from a CleanResult and render it as Markdown."""

from collections import Counter


def build_report(result):
    """Compute report statistics from a CleanResult. Returns a plain dict."""
    clean = result.clean_rows

    issue_counts = dict(Counter(i.issue_type for i in result.detected_issues))
    rows_with_issue = len({i.row_index for i in result.detected_issues})

    by_type = dict(Counter(r["claim_type"] for r in clean if r["claim_type"]))
    by_status = dict(Counter(r["status"] for r in clean if r["status"]))

    # Average amount by claim type, kept SEPARATE per currency — THB and VND are
    # different denominations and must never be averaged together.
    sums, counts = Counter(), Counter()
    for r in clean:
        if r["submitted_amount"] is not None and r["currency"]:
            key = (r["claim_type"], r["currency"])
            sums[key] += r["submitted_amount"]
            counts[key] += 1
    avg_amount_by_type_currency = {k: round(sums[k] / counts[k], 2) for k in counts}

    # Top 5 diagnoses, merged case-insensitively, displayed in first-seen casing,
    # excluding null/N/A (already None after cleaning).
    diag_counts, diag_display = Counter(), {}
    for r in clean:
        d = r["diagnosis"]
        if not d:
            continue
        key = d.lower()
        diag_counts[key] += 1
        diag_display.setdefault(key, d)
    top_diagnoses = [(diag_display[k], c) for k, c in diag_counts.most_common(5)]

    return {
        "rows_before": result.rows_before,
        "rows_after": len(clean),
        "duplicates_removed": result.duplicates_removed,
        "quarantined": len(result.quarantine_rows),
        "issue_counts": issue_counts,
        "rows_with_issue": rows_with_issue,
        "by_type": by_type,
        "by_status": by_status,
        "avg_amount_by_type_currency": avg_amount_by_type_currency,
        "top_diagnoses": top_diagnoses,
    }


def render_markdown(rep):
    """Render a report dict (from build_report) as a Markdown document."""
    lines = ["# Data Quality Report", ""]
    lines += [
        f"- **Rows before cleaning:** {rep['rows_before']}",
        f"- **Rows after cleaning:** {rep['rows_after']}",
        f"- **Exact duplicates removed:** {rep['duplicates_removed']}",
        f"- **Rows quarantined:** {rep['quarantined']}",
        f"- **Rows with at least one issue:** {rep['rows_with_issue']}",
        "",
        "## Issues by type",
    ]
    lines += [f"- `{t}`: {c}" for t, c in sorted(rep["issue_counts"].items())] or ["- (none)"]

    lines += ["", "## Claims by type"]
    lines += [f"- {k}: {v}" for k, v in sorted(rep["by_type"].items())] or ["- (none)"]

    lines += ["", "## Claims by status"]
    lines += [f"- {k}: {v}" for k, v in sorted(rep["by_status"].items())] or ["- (none)"]

    lines += ["", "## Average amount by type (per currency)"]
    lines += [
        f"- {ct} ({cur}): {v:,.2f}"
        for (ct, cur), v in sorted(rep["avg_amount_by_type_currency"].items())
    ] or ["- (none)"]

    lines += ["", "## Top 5 diagnoses"]
    lines += [f"- {n}: {c}" for n, c in rep["top_diagnoses"]] or ["- (none)"]

    return "\n".join(lines) + "\n"
