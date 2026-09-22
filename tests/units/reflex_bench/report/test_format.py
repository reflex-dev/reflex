"""Tests for reflex_bench.report.format."""

from __future__ import annotations

import pytest
from reflex_bench.report import format as fmt
from reflex_bench.schema import ComparisonDoc


@pytest.mark.parametrize(
    ("value", "unit", "expected"),
    [
        (0.05021, "s", "50.21 ms"),
        (1.002, "s", "1.002 s"),
        (75.2, "s", "75.20 s"),
        (0.0000123, "s", "12.30 \N{MICRO SIGN}s"),
        (0.0000000042, "s", "4.200 ns"),
        (0.0, "s", "0.000 s"),
        (238_400, "B", "238.4 kB"),
        (512, "B", "512 B"),
        (3_500_000_000, "B", "3.500 GB"),
        (12_345.6, "ev/s", "12,346 ev/s"),
        (56.789, "ev/s", "56.79 ev/s"),
        (1234, "1", "1,234"),
        (2.5, "1", "2.500"),
    ],
)
def test_format_value_scales_to_four_significant_digits(value, unit, expected):
    assert fmt.format_value(value, unit) == expected


def test_a_row_shares_one_scale():
    scale = fmt.scale_for("s", 0.9968, 0.9045, 1.1596)
    assert (scale.label, scale.decimals) == ("s", 3)
    assert fmt.format_value(0.9968, "s", scale) == "0.997 s"
    assert fmt.format_value(1.1596, "s", scale) == "1.160 s"


@pytest.mark.parametrize(
    ("fraction", "expected"),
    [(0.054, "+5.4 %"), (0.17, "+17 %"), (-0.026, "-2.6 %"), (0.0, "+0.0 %")],
)
def test_format_pct(fraction, expected):
    assert fmt.format_pct(fraction) == expected


def test_percent_helpers():
    assert fmt.format_pct(0.03, signed=False) == "3.0 %"
    assert fmt.format_change_ci([0.049, 0.059]) == "[+4.9, +5.9]"
    assert fmt.format_change_ci([-0.012, 0.17]) == "[-1.2, +17]"
    assert (
        fmt.format_ci_width(0.05021, [0.05015, 0.0504]) == "\N{PLUS-MINUS SIGN} 0.4 %"
    )
    assert fmt.format_ci_width(1.0, None) == ""


@pytest.mark.parametrize(
    ("p", "expected"),
    [(0.00001, "p=0.000"), (0.004, "p=0.004"), (0.71, "p=0.71"), (None, "p=n/a")],
)
def test_format_p(p, expected):
    assert fmt.format_p(p) == expected


def _comparison(**changes) -> ComparisonDoc:
    comparison: ComparisonDoc = {
        "base": {
            "invocation_id": "a",
            "arm": "A",
            "n": 10,
            "median": 1.0,
            "ci": [0.99, 1.01],
        },
        "head": {
            "invocation_id": "b",
            "arm": "A",
            "n": 10,
            "median": 1.05,
            "ci": [1.04, 1.06],
        },
        "ratio": 0.054,
        "ci": [0.049, 0.059],
        "p": 0.0001,
        "p_adj": 0.0002,
        "test": "mwu-exact",
        "threshold_rel": 0.03,
        "verdict": "regressed",
        "runs_needed": None,
    }
    comparison.update(changes)  # pyright: ignore[reportCallIssue, reportArgumentType]
    return comparison


def test_comparison_texts():
    regressed = _comparison()
    assert fmt.change_text(regressed, exact=False) == "+5.4 % [+4.9, +5.9]"
    assert fmt.stats_text(regressed, exact=False) == "p=0.000 n=10/10"
    assert fmt.verdict_text(regressed, exact=False) == "regressed"

    unchanged = _comparison(verdict="unchanged", ratio=-0.003, ci=[-0.026, 0.019])
    assert fmt.change_text(unchanged, exact=False) == "~ [-2.6, +1.9]"
    assert fmt.verdict_text(unchanged, exact=False) == "no change"
    assert fmt.verdict_text(unchanged, exact=True) == "~ below threshold"

    exact = _comparison(verdict="unchanged", ratio=0.011, ci=None, p=None, p_adj=None)
    assert fmt.change_text(exact, exact=True) == "+1.1 %"
    assert fmt.stats_text(exact, exact=True) == "exact"

    inconclusive = _comparison(verdict="inconclusive", runs_needed=40)
    assert fmt.verdict_text(inconclusive, exact=False) == (
        "? inconclusive (~40 runs/side needed)"
    )
    assert fmt.verdict_text(
        _comparison(verdict="inconclusive", runs_needed=200), exact=False
    ) == ("? inconclusive (200+ runs/side needed)")
    assert fmt.change_text(_comparison(ratio=None), exact=True) == "n/a (zero base)"
    assert fmt.verdict_style("regressed") == "bold red"
    assert fmt.verdict_style("unchanged") == ""
