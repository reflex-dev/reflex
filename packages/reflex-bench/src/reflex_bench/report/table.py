"""Terminal reports: the run header, the result table and the comparison table.

Columns are laid out by hand rather than with a ``rich.table.Table`` so that
full-width lines (warnings, failures) sit between rows without widening a
column. Everything is printed as :class:`rich.text.Text`, never as markup,
because instance names contain brackets.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from typing import IO

from rich.console import Console
from rich.text import Text

from reflex_bench import compare
from reflex_bench.machine import LOAD_WARN, short_cpu_model
from reflex_bench.report.format import (
    ALPHA,
    CROSS,
    DOT,
    ELLIPSIS,
    EN_DASH,
    PLUS_MINUS,
    WARN,
    Scale,
    change_text,
    format_ci_width,
    format_estimate,
    format_pct,
    format_value,
    scale_for,
    stats_text,
    verdict_style,
    verdict_text,
)
from reflex_bench.schema import (
    ComparedToDoc,
    ComparisonSideDoc,
    FailedInHeadDoc,
    MachineDoc,
    PolicyDoc,
    ResultDoc,
    SubjectDoc,
    entry_name,
    timed_values,
)

_GAP = "   "
_SEPARATOR = f" {DOT} "
Cell = str | Text
Line = Text | list[Cell]


def make_console(
    *,
    plain: bool = False,
    stderr: bool = False,
    file: IO[str] | None = None,
    width: int | None = None,
) -> Console:
    """Create the console reports print to.

    Args:
        plain: No colors (CI and tests).
        stderr: Print to standard error instead of standard output.
        file: Print to this file instead.
        width: A fixed width; lines are never wrapped either way.

    Returns:
        The console.
    """
    return Console(
        file=file,
        stderr=stderr,
        width=width,
        color_system=None if plain else "auto",
        no_color=plain,
        highlight=False,
        emoji=False,
        soft_wrap=True,
    )


def _print_lines(
    console: Console, lines: Sequence[Line], right: Sequence[int] = ()
) -> None:
    """Print rows in aligned columns, with full-width lines in between.

    Args:
        console: Where to print.
        lines: Rows (lists of cells) and full-width lines (texts).
        right: Indices of right-aligned columns.
    """
    rows = [line for line in lines if isinstance(line, list)]
    widths = [
        max((len(row[i]) for row in rows if i < len(row)), default=0)
        for i in range(max((len(row) for row in rows), default=0))
    ]
    for line in lines:
        if isinstance(line, Text):
            console.print(line)
            continue
        text = Text()
        for i, cell in enumerate(line):
            if i:
                text.append(_GAP)
            pad = " " * (widths[i] - len(cell))
            cell_text = cell if isinstance(cell, Text) else Text(cell)
            if i in right:
                text.append(pad).append_text(cell_text)
            elif i < len(line) - 1:
                text.append_text(cell_text).append(pad)
            else:
                text.append_text(cell_text)
        text.rstrip()
        console.print(text)


def subject_label(subject: SubjectDoc) -> str:
    """Describe a subject for a header.

    Args:
        subject: The subject entry.

    Returns:
        E.g. ``reflex 0.9.12 (workspace 258d66c, dirty)``.
    """
    details = subject["spec"] + (
        f" {subject['commit'][:7]}" if subject["commit"] else ""
    )
    if subject["dirty"]:
        details += ", dirty"
    return f"reflex {subject['reflex_version'] or 'not installed'} ({details})"


def machine_line(machine: MachineDoc) -> str:
    """Describe the machine in one line, flagging noisy settings.

    Args:
        machine: The machine entry.

    Returns:
        E.g. ``machine: linux-x86_64 · AMD Ryzen 9 7950X · 32 cores · load 0.4``.
    """
    parts = [
        f"{machine['os'].lower()}-{machine['arch']}",
        short_cpu_model(machine["cpu_model"]),
    ]
    if machine["cpu_count"]:
        parts.append(f"{machine['cpu_count']} cores")
    governor = machine["governor"]
    if governor:
        parts.append(
            f"governor={governor}" + ("" if governor == "performance" else f" {WARN}")
        )
    if machine["turbo"] is not None:
        parts.append(
            f"turbo={'on' if machine['turbo'] else 'off'}"
            + (f" {WARN}" if machine["turbo"] else "")
        )
    if machine["virtualized"]:
        parts.append(f"vm {WARN}")
    if machine["ac_power"] is False:
        parts.append(f"battery {WARN}")
    load = machine["load_avg_1m"]
    if load is not None:
        parts.append(f"load {load:g}" + (f" {WARN}" if load > LOAD_WARN else ""))
    return "machine: " + _SEPARATOR.join(parts)


def policy_line(policy: PolicyDoc, seed: int) -> str:
    """Describe every effective setting in one line.

    Args:
        policy: The policy entry.
        seed: The invocation seed.

    Returns:
        E.g. ``policy: runs 10-30, min-time 30 s, ..., seed 1234`` (with an en dash).
    """
    if policy["smoke"]:
        runs = "smoke (1 run, no warmup, no statistics)"
    elif policy["runs"] is not None:
        runs = f"runs {policy['runs']} (fixed)"
    else:
        runs = (
            f"runs {policy['min_runs']}{EN_DASH}{policy['max_runs']},"
            f" min-time {policy['min_time_s']:g} s"
        )
    warmup = (
        "warmup per benchmark"
        if policy["warmup"] is None
        else f"warmup {policy['warmup']}"
    )
    timeout = (
        "timeout per benchmark"
        if policy["timeout_s"] is None
        else f"timeout {policy['timeout_s']:g} s"
    )
    fail_on = f"fail-on {policy['fail_on']}" + (
        " and inconclusive" if policy["fail_on_inconclusive"] else ""
    )
    return (
        f"policy: {runs}, {warmup}, {timeout},"
        f" {ALPHA}={policy['alpha']:g} ({policy['correction'].title()}),"
        f" threshold {100 * policy['threshold_rel']:g} %, CI {100 * policy['confidence']:g} %,"
        f" bootstrap {policy['bootstrap_resamples']}, seed {seed}, {fail_on}"
    )


def render_header(console: Console, doc: ResultDoc, doctor_warnings: int) -> None:
    """Print the run header: tool, subject, machine and policy.

    Args:
        console: Where to print.
        doc: The result document.
        doctor_warnings: How many ``doctor`` checks warn.
    """
    subject = doc["subjects"]["A"]
    console.print(
        Text(
            f"reflex-bench {doc['tool']['version']}{_SEPARATOR}{subject_label(subject)}"
            f"{_SEPARATOR}py {subject['python_version']}"
        )
    )
    console.print(Text(machine_line(doc["machine"])))
    console.print(Text(policy_line(doc["policy"], doc["invocation"]["rng_seed"])))
    if doctor_warnings:
        plural = "s" if doctor_warnings > 1 else ""
        console.print(
            Text(
                f"{WARN} {doctor_warnings} doctor warning{plural}: expect {PLUS_MINUS}3{EN_DASH}5 %"
                " extra variance (run `reflex-bench doctor`)",
                style="yellow",
            )
        )
    console.print()


def _status_line(status: str, error: str | None) -> Text:
    """Describe an instance that did not produce statistics.

    Args:
        status: The instance status.
        error: Its error message.

    Returns:
        An indented, styled line.
    """
    marker = EN_DASH if status in {"unsupported", "skipped"} else CROSS
    style = "yellow" if status in {"unsupported", "skipped"} else "red"
    return Text(f"  {marker} {status}" + (f": {error}" if error else ""), style=style)


def render_run(console: Console, doc: ResultDoc) -> None:
    """Print the result table: median with CI, range and sample count per metric.

    Args:
        console: Where to print.
        doc: The result document.
    """
    policy = doc["policy"]
    header = [f"median {PLUS_MINUS} {100 * policy['confidence']:g} % CI", "range", "n"]
    lines: list[Line] = []
    for entry in doc["benchmarks"]:
        lines.append([Text(entry_name(entry), style="bold"), *(header or ["", "", ""])])
        header = []
        if entry["status"] != "ok":
            lines.append(_status_line(entry["status"], entry["error"]))
            continue
        for name, metric in entry["metrics"].items():
            exact = metric["assume"] == "exact"
            if policy["smoke"]:
                values = timed_values(entry, name)
                if values:
                    shown = format_value(values[0], metric["unit"])
                    lines.append([
                        f"  {name}",
                        f"{shown} (smoke)",
                        "",
                        str(len(values)),
                    ])
                continue
            arms = sorted(metric["summary"])
            for arm in arms:
                summary = metric["summary"][arm]
                scale = scale_for(metric["unit"], summary["min"], summary["max"])
                label = f"  {name}" if len(arms) == 1 else f"  {name} [{arm}]"
                spread = (
                    ""
                    if exact
                    else f"{format_value(summary['min'], metric['unit'], scale)} {ELLIPSIS}"
                    f" {format_value(summary['max'], metric['unit'], scale)}"
                )
                lines.append([
                    label,
                    format_estimate(
                        summary, metric["unit"], exact, scale, policy["confidence"]
                    ),
                    spread,
                    str(summary["n"]),
                ])
            lines.extend(
                Text(f"  {WARN} {warning}", style="yellow")
                for warning in metric["warnings"]
            )
    _print_lines(console, lines, right=(3,))
    statuses = Counter(entry["status"] for entry in doc["benchmarks"])
    if set(statuses) - {"ok"}:
        total = len(doc["benchmarks"])
        console.print()
        console.print(
            Text(
                f"{total} benchmark{'' if total == 1 else 's'}: "
                + _SEPARATOR.join(
                    f"{count} {status}" for status, count in statuses.items()
                )
            )
        )


def _side_text(side: ComparisonSideDoc, unit: str, exact: bool, scale: Scale) -> str:
    """Format one side of a comparison.

    Args:
        side: The side.
        unit: The metric unit.
        exact: Whether the metric is deterministic.
        scale: The row's scale.

    Returns:
        E.g. ``50.21 ms ± 0.4 %``.
    """
    value = format_value(side["median"], unit, scale)
    width = "" if exact else format_ci_width(side["median"], side["ci"])
    return f"{value} {width}" if width else value


def geomean_line(doc: ResultDoc) -> str | None:
    """Summarize the changes of an annotated document per unit family.

    Args:
        doc: The head document after :func:`reflex_bench.compare.compare`.

    Returns:
        E.g. ``geomean (time) +2.1 % · geomean (bytes) +1.1 %``, or ``None``.
    """
    means = compare.geomeans(doc)
    if not means:
        return None
    return _SEPARATOR.join(
        f"geomean ({family}) {format_pct(mean)}" for family, mean in means.items()
    )


def counts_line(doc: ResultDoc) -> str:
    """Count the verdicts of an annotated document.

    Args:
        doc: The head document after :func:`reflex_bench.compare.compare`.

    Returns:
        E.g. ``1 regressed · 0 improved · 1 inconclusive · 2 unchanged``, followed
        by ``· 1 failed in head`` when entries started failing.
    """
    counts = compare.verdict_counts(doc)
    line = _SEPARATOR.join(
        f"{counts.get(verdict, 0)} {verdict}"
        for verdict in ("regressed", "improved", "inconclusive", "unchanged")
    )
    if failed := compare.failed_in_head(doc):
        line += f"{_SEPARATOR}{len(failed)} failed in head"
    return line


def failure_text(failure: FailedInHeadDoc) -> str:
    """Describe how an entry started failing in head, after its verdict.

    Args:
        failure: The entry.

    Returns:
        E.g. ``(ok in base, failed in head): RuntimeError: boom``.
    """
    origin = (
        "new" if failure["base_status"] is None else f"{failure['base_status']} in base"
    )
    error = f": {failure['error']}" if failure["error"] else ""
    return f"({origin}, {failure['status']} in head){error}"


def significance_label(compared_to: ComparedToDoc) -> str:
    """Describe the significance level and its correction.

    Args:
        compared_to: The comparison settings.

    Returns:
        E.g. ``alpha=0.01 (Holm, 4 metrics)``, with a Greek alpha.
    """
    size = compared_to["family_size"]
    return f"{ALPHA}={compared_to['alpha']:g} (Holm, {size} metric{'' if size == 1 else 's'})"


def render_comparison(console: Console, doc: ResultDoc) -> None:
    """Print the comparison table of an annotated document.

    Args:
        console: Where to print.
        doc: The head document after :func:`reflex_bench.compare.compare`.
    """
    compared_to = doc.get("compared_to")
    if compared_to is None:
        return
    forced = "  (forced: series keys not checked)" if compared_to["forced"] else ""
    console.print(
        Text(
            f"reflex-bench compare {compared_to['base_label']} {compared_to['head_label']}"
            f"   {significance_label(compared_to)}"
            f"  threshold={100 * compared_to['threshold_rel']:g} %{forced}"
        )
    )
    console.print()
    lines: list[Line] = [["", "", "base", "head", "", "", ""]]
    previous = None
    for row in compare.rows(doc):
        exact = row.doc["assume"] == "exact"
        comparison = row.comparison
        scale = scale_for(
            row.doc["unit"], comparison["base"]["median"], comparison["head"]["median"]
        )
        verdict = comparison["verdict"]
        lines.append([
            row.name if row.name != previous else "",
            row.metric,
            _side_text(comparison["base"], row.doc["unit"], exact, scale),
            _side_text(comparison["head"], row.doc["unit"], exact, scale),
            change_text(comparison, exact, scale),
            stats_text(comparison, exact),
            Text(verdict_text(comparison, exact), style=verdict_style(verdict)),
        ])
        previous = row.name
    if previous is None:
        console.print(
            Text(
                "nothing compared: no benchmark has samples on both sides"
                " with matching series keys",
                style="yellow",
            )
        )
    else:
        _print_lines(console, lines)
    if geomean := geomean_line(doc):
        console.print(Text(geomean))
    console.print(Text(counts_line(doc)))
    for failure in compare.failed_in_head(doc):
        console.print(
            Text(
                f"{CROSS} {failure['id']}: regressed {failure_text(failure)}",
                style=verdict_style("regressed"),
            )
        )
    for label, names in (
        ("only in base", compared_to["only_in_base"]),
        ("only in head", compared_to["only_in_head"]),
    ):
        if names:
            console.print(Text(f"{label}: {', '.join(names)}", style="yellow"))
    for item in compared_to["not_comparable"]:
        console.print(
            Text(
                f"not compared: {item['id']}: {'; '.join(item['reasons'])}",
                style="yellow",
            )
        )


def render_samples(console: Console, doc: ResultDoc) -> None:
    """Print every raw sample, warmups marked.

    Args:
        console: Where to print.
        doc: The result document.
    """
    for entry in doc["benchmarks"]:
        for name, metric in entry["metrics"].items():
            for arm, values in metric["samples"].items():
                metas = [meta for meta in entry["sample_meta"] if meta["arm"] == arm]
                if not values:
                    continue
                scale = scale_for(metric["unit"], *values)
                console.print(
                    Text(f"{entry_name(entry)} {DOT} {name} [{arm}]", style="bold")
                )
                for index, (value, meta) in enumerate(zip(values, metas, strict=True)):
                    tag = "  warmup" if meta["warmup"] else ""
                    console.print(
                        Text(
                            f"  {index:>4}  {format_value(value, metric['unit'], scale)}{tag}"
                        )
                    )
