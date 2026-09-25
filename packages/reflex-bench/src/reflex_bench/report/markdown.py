"""Markdown reports for pull request comments.

A comparison lists regressed, improved and inconclusive metrics first and folds
the unchanged ones into a ``<details>`` block, so the comment leads with what
needs attention.
"""

from __future__ import annotations

from collections.abc import Sequence

from reflex_bench import compare
from reflex_bench.report.format import (
    ELLIPSIS,
    PLUS_MINUS,
    change_text,
    format_ci_width,
    format_estimate,
    format_value,
    scale_for,
    stats_text,
    verdict_text,
)
from reflex_bench.report.table import (
    counts_line,
    failure_text,
    geomean_line,
    significance_label,
    subject_label,
)
from reflex_bench.schema import ResultDoc, entry_name

_COMPARISON_HEADER = (
    "Benchmark",
    "Metric",
    "Base",
    "Head",
    "Change",
    "Test",
    "Verdict",
)


def _escape(cell: str) -> str:
    """Escape a table cell.

    Args:
        cell: The cell text.

    Returns:
        The text with pipes escaped and newlines flattened.
    """
    return cell.replace("|", "\\|").replace("\n", " ")


def _table(header: Sequence[str], rows: Sequence[Sequence[str]]) -> list[str]:
    """Build a GitHub markdown table.

    Args:
        header: The column titles.
        rows: The cells.

    Returns:
        The table lines.
    """
    return [
        "| " + " | ".join(header) + " |",
        "|" + "---|" * len(header),
        *("| " + " | ".join(_escape(cell) for cell in row) + " |" for row in rows),
    ]


def render_comparison(doc: ResultDoc) -> str:
    """Render the comparison of an annotated document as markdown.

    Args:
        doc: The head document after :func:`reflex_bench.compare.compare`.

    Returns:
        The markdown text.
    """
    compared_to = doc.get("compared_to")
    if compared_to is None:
        return render_result(doc)
    attention: list[list[str]] = []
    unchanged: list[list[str]] = []
    for row in compare.rows(doc):
        exact = row.doc["assume"] == "exact"
        comparison = row.comparison
        unit = row.doc["unit"]
        scale = scale_for(
            unit, comparison["base"]["median"], comparison["head"]["median"]
        )
        sides = []
        for side in (comparison["base"], comparison["head"]):
            width = "" if exact else format_ci_width(side["median"], side["ci"])
            sides.append(f"{format_value(side['median'], unit, scale)} {width}".strip())
        verdict = verdict_text(comparison, exact)
        if comparison["verdict"] == "regressed":
            verdict = f"**{verdict}**"
        cells = [
            f"`{row.name}`",
            row.metric,
            *sides,
            change_text(comparison, exact, scale),
            stats_text(comparison, exact),
            verdict,
        ]
        (unchanged if comparison["verdict"] == "unchanged" else attention).append(cells)
    lines = [
        f"### reflex-bench: {counts_line(doc)}",
        "",
        (
            f"`{compared_to['base_label']}` vs `{compared_to['head_label']}`:"
            f" {significance_label(compared_to)},"
            f" threshold {100 * compared_to['threshold_rel']:g} %"
        ),
        "",
    ]
    failures = compare.failed_in_head(doc)
    if failures:
        lines += [
            "Failed in head:",
            *(
                f"- `{failure['id']}`: **regressed** {failure_text(failure)}"
                for failure in failures
            ),
            "",
        ]
    if attention:
        lines += [*_table(_COMPARISON_HEADER, attention), ""]
    elif not failures:
        lines += [
            "No regressions, improvements or inconclusive results."
            if unchanged
            else "No comparable metrics.",
            "",
        ]
    if geomean := geomean_line(doc):
        lines.append(geomean)
    if unchanged:
        lines += [
            "",
            f"<details><summary>{len(unchanged)} unchanged</summary>",
            "",
            *_table(_COMPARISON_HEADER, unchanged),
            "",
            "</details>",
        ]
    for label, names in (
        ("Only in base", compared_to["only_in_base"]),
        ("Only in head", compared_to["only_in_head"]),
    ):
        if names:
            lines += ["", f"{label}: " + ", ".join(f"`{name}`" for name in names)]
    if compared_to["not_comparable"]:
        lines += ["", "Not compared:"]
        lines += [
            f"- `{item['id']}`: {'; '.join(item['reasons'])}"
            for item in compared_to["not_comparable"]
        ]
    return "\n".join(lines).rstrip() + "\n"


def render_result(doc: ResultDoc) -> str:
    """Render a result without a comparison as a markdown table.

    Args:
        doc: The result document.

    Returns:
        The markdown text.
    """
    confidence = doc["policy"]["confidence"]
    rows: list[list[str]] = []
    for entry in doc["benchmarks"]:
        name = f"`{entry_name(entry)}`"
        if entry["status"] != "ok":
            rows.append([name, "", entry["status"], entry["error"] or "", ""])
            continue
        for metric_name, metric in entry["metrics"].items():
            summary = metric["summary"].get("A")
            if summary is None:
                continue
            scale = scale_for(metric["unit"], summary["min"], summary["max"])
            exact = metric["assume"] == "exact"
            spread = (
                ""
                if exact
                else f"{format_value(summary['min'], metric['unit'], scale)} {ELLIPSIS}"
                f" {format_value(summary['max'], metric['unit'], scale)}"
            )
            rows.append([
                name,
                metric_name,
                format_estimate(summary, metric["unit"], exact, scale, confidence),
                spread,
                str(summary["n"]),
            ])
    header = (
        "Benchmark",
        "Metric",
        f"Median {PLUS_MINUS} {100 * confidence:g} % CI",
        "Range",
        "n",
    )
    subject = doc["subjects"]["A"]
    return "\n".join([
        f"### reflex-bench: {subject_label(subject)}",
        "",
        f"Machine `{doc['machine']['profile_id']}`",
        "",
        *_table(header, rows),
        "",
    ])
