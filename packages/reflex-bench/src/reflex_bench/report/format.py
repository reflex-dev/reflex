"""Display formatting shared by the terminal and markdown reports.

Data is stored in SI base units; scaling to ms, kB and friends happens only
here. All values of one table row share one scale, so they stay comparable.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import NamedTuple

from reflex_bench.schema import ComparisonDoc, SummaryDoc
from reflex_bench.stats import RUNS_NEEDED_CAP, min_ci_samples

ALPHA = "\N{GREEK SMALL LETTER ALPHA}"
DOT = "\N{MIDDLE DOT}"
ELLIPSIS = "\N{HORIZONTAL ELLIPSIS}"
EN_DASH = "\N{EN DASH}"
GEQ = "\N{GREATER-THAN OR EQUAL TO}"
PLUS_MINUS = "\N{PLUS-MINUS SIGN}"
WARN = "\N{WARNING SIGN}"
CROSS = "\N{BALLOT X}"

_TIME_SCALES = ((1.0, "s"), (1e-3, "ms"), (1e-6, "\N{MICRO SIGN}s"), (1e-9, "ns"))
_BYTE_SCALES = ((1e9, "GB"), (1e6, "MB"), (1e3, "kB"), (1.0, "B"))
_SIGNIFICANT = 4


class Scale(NamedTuple):
    """How to display the values of one row."""

    factor: float
    label: str
    decimals: int


def scale_for(unit: str, *values: float) -> Scale:
    """Choose one display scale for all values of a row.

    Args:
        unit: The SI base unit of the data.
        *values: The values the row shows (medians, ranges).

    Returns:
        The factor to divide by, the unit label and the decimals that give four
        significant digits at the largest value (whole numbers for bytes and for
        whole counts).
    """
    magnitude = max((abs(value) for value in values), default=0.0)
    scales = _TIME_SCALES if unit == "s" else _BYTE_SCALES if unit == "B" else ()
    factor, label = next(
        ((f, name) for f, name in scales if magnitude >= f),
        (1.0, unit) if not magnitude or not scales else scales[-1],
    )
    if label == "B":
        return Scale(factor, label, 0)
    if unit == "1" and all(float(value).is_integer() for value in values):
        return Scale(factor, label, 0)
    scaled = magnitude / factor
    digits = len(str(int(scaled))) if scaled >= 1 else 1
    return Scale(factor, label, max(0, _SIGNIFICANT - digits))


def format_value(value: float, unit: str, scale: Scale | None = None) -> str:
    """Format a value with its unit.

    Args:
        value: The value in SI base units.
        unit: The unit.
        scale: The row's scale; defaults to one chosen for this value.

    Returns:
        E.g. ``50.21 ms``, ``238.4 kB`` or ``12,346 ev/s``.
    """
    scale = scale or scale_for(unit, value)
    text = f"{value / scale.factor:,.{scale.decimals}f}"
    return text if scale.label == "1" else f"{text} {scale.label}"


def _percent(fraction: float, signed: bool) -> str:
    """Format a fraction as a percentage number: one decimal below 10 %.

    Args:
        fraction: The fraction (``0.054`` is 5.4 %).
        signed: Whether to always show the sign.

    Returns:
        The number without the percent sign.
    """
    value = 100 * fraction
    decimals = 1 if abs(value) < 10 else 0
    return f"{value:+.{decimals}f}" if signed else f"{value:.{decimals}f}"


def format_pct(fraction: float, signed: bool = True) -> str:
    """Format a fraction as a percentage.

    Args:
        fraction: The fraction.
        signed: Whether to always show the sign.

    Returns:
        E.g. ``+5.4 %`` or ``+17 %``.
    """
    return f"{_percent(fraction, signed)} %"


def format_change_ci(ci: Sequence[float]) -> str:
    """Format the CI of a relative change.

    Args:
        ci: ``[low, high]`` fractions.

    Returns:
        E.g. ``[+4.9, +5.9]`` (percent).
    """
    return f"[{_percent(ci[0], True)}, {_percent(ci[1], True)}]"


def format_ci_width(median: float, ci: Sequence[float] | None) -> str:
    """Format the worse side of a median CI relative to the median.

    Args:
        median: The median.
        ci: Its ``[low, high]`` interval.

    Returns:
        E.g. ``± 0.4 %``, or an empty string without a CI.
    """
    if ci is None or not median:
        return ""
    width = max(median - ci[0], ci[1] - median) / abs(median)
    return f"{PLUS_MINUS} {format_pct(width, signed=False)}"


def format_estimate(
    summary: SummaryDoc, unit: str, exact: bool, scale: Scale, confidence: float
) -> str:
    """Format a median with its CI width, as in the ``median ± 95 % CI`` column.

    Args:
        summary: The summary.
        unit: The metric unit.
        exact: Whether the metric is deterministic.
        scale: The row's scale.
        confidence: The confidence level of the CI.

    Returns:
        E.g. ``50.21 ms ± 0.4 %``, ``238.4 kB (exact)`` or
        ``50.21 ms (need ≥ 6 samples)``.
    """
    value = format_value(summary["median"], unit, scale)
    if exact:
        return f"{value} (exact)"
    if summary["ci"] is None:
        return f"{value} (need {GEQ} {min_ci_samples(confidence)} samples)"
    return f"{value} {format_ci_width(summary['median'], summary['ci'])}"


def format_p(p: float | None) -> str:
    """Format a p-value.

    Args:
        p: The p-value.

    Returns:
        E.g. ``p=0.000``, ``p=0.004`` or ``p=0.71``.
    """
    if p is None:
        return "p=n/a"
    return f"p={p:.3f}" if p < 0.01 else f"p={p:.2f}"


def change_text(comparison: ComparisonDoc, exact: bool) -> str:
    """Format the change column of a comparison.

    Args:
        comparison: The comparison.
        exact: Whether the metric is deterministic.

    Returns:
        E.g. ``+5.4 % [+4.9, +5.9]``, ``~ [-2.6, +1.9]`` or ``+1.1 %``.
    """
    ratio, ci = comparison["ratio"], comparison["ci"]
    if ratio is None:
        return "n/a (zero base)"
    if exact or ci is None:
        return format_pct(ratio)
    if comparison["verdict"] == "unchanged":
        return f"~ {format_change_ci(ci)}"
    return f"{format_pct(ratio)} {format_change_ci(ci)}"


def stats_text(comparison: ComparisonDoc, exact: bool) -> str:
    """Format the test column of a comparison.

    Args:
        comparison: The comparison.
        exact: Whether the metric is deterministic.

    Returns:
        E.g. ``p=0.000 n=10/10``, or ``exact`` for deterministic metrics.
    """
    if exact:
        return "exact"
    counts = f"n={comparison['base']['n']}/{comparison['head']['n']}"
    return f"{format_p(comparison['p_adj'])} {counts}"


def verdict_text(comparison: ComparisonDoc, exact: bool) -> str:
    """Format the verdict of a comparison.

    Args:
        comparison: The comparison.
        exact: Whether the metric is deterministic.

    Returns:
        E.g. ``regressed``, ``no change``, ``~ below threshold`` or
        ``? inconclusive (~40 runs/side needed)``.
    """
    verdict = comparison["verdict"]
    if verdict == "unchanged":
        return "~ below threshold" if exact else "no change"
    if verdict != "inconclusive":
        return verdict
    needed = comparison["runs_needed"]
    if needed is None:
        return "? inconclusive"
    if needed >= RUNS_NEEDED_CAP:
        return f"? inconclusive ({needed}+ runs/side needed)"
    return f"? inconclusive (~{needed} runs/side needed)"


def verdict_style(verdict: str) -> str:
    """Pick the terminal style of a verdict.

    Args:
        verdict: The verdict.

    Returns:
        A rich style name.
    """
    return {"regressed": "bold red", "improved": "green", "inconclusive": "yellow"}.get(
        verdict, ""
    )
