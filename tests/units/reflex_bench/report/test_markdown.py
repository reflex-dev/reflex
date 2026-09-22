"""Tests for reflex_bench.report.markdown."""

from __future__ import annotations

from reflex_bench import compare
from reflex_bench.registry import Metric
from reflex_bench.report import markdown

from tests.units.reflex_bench.factories import WALL, make_doc, make_entry

EXACT = Metric(unit="B", direction="lower", assume="exact")
SLEEP = [
    0.05008,
    0.05015,
    0.05018,
    0.0502,
    0.05021,
    0.05021,
    0.05023,
    0.0503,
    0.0504,
    0.05061,
]
HEADER = "| Benchmark | Metric | Base | Head | Change | Test | Verdict |"


def _compared(head_factor: float) -> str:
    base = make_doc([
        make_entry("selftest.sleep", {"wall": (WALL, SLEEP)}, params={"ms": 50}),
        make_entry("selftest.exact", {"bytes": (EXACT, [238_400])}),
        make_entry("selftest.gone", {"wall": (WALL, SLEEP)}),
    ])
    head = make_doc([
        make_entry(
            "selftest.sleep",
            {"wall": (WALL, [v * head_factor for v in SLEEP])},
            params={"ms": 50},
        ),
        make_entry("selftest.exact", {"bytes": (EXACT, [238_400])}),
    ])
    compare.compare(
        base,
        head,
        threshold=0.03,
        alpha=0.01,
        resamples=2000,
        seed=1,
        base_label="0041",
        head_label="this run",
    )
    return markdown.render_comparison(head)


def test_attention_rows_first_and_unchanged_folded():
    text = _compared(1.054)
    lines = text.splitlines()
    assert lines[0] == (
        "### reflex-bench: 1 regressed \N{MIDDLE DOT} 0 improved \N{MIDDLE DOT}"
        " 0 inconclusive \N{MIDDLE DOT} 1 unchanged"
    )
    assert lines[2] == (
        "`0041` vs `this run`: \N{GREEK SMALL LETTER ALPHA}=0.01 (Holm, 1 metric),"
        " threshold 3 %"
    )
    assert lines[4] == HEADER
    assert lines[5] == "|---|---|---|---|---|---|---|"
    assert lines[6].startswith("| `selftest.sleep[ms=50]` | wall | 50.21 ms")
    assert lines[6].endswith("| **regressed** |")
    details = text.index("<details><summary>1 unchanged</summary>")
    assert text.index("`selftest.exact`") > details
    assert text.rstrip().endswith("Only in base: `selftest.gone`")


def test_all_unchanged_says_so():
    text = _compared(1.0)
    assert "No regressions, improvements or inconclusive results." in text
    assert "<details><summary>2 unchanged</summary>" in text


def test_cells_are_escaped():
    assert markdown._escape("a|b\nc") == "a\\|b c"


def test_result_without_comparison():
    doc = make_doc([
        make_entry("selftest.sleep", {"wall": (WALL, SLEEP)}, params={"ms": 50}),
        make_entry(
            "selftest.fail",
            {"wall": (WALL, [])},
            status="failed",
            error="RuntimeError: boom",
        ),
    ])
    text = markdown.render_comparison(doc)
    lines = text.splitlines()
    assert lines[0] == "### reflex-bench: reflex 0.9.12 (workspace 258d66c, dirty)"
    assert lines[2] == "Machine `test-profile`"
    assert (
        lines[4]
        == "| Benchmark | Metric | Median \N{PLUS-MINUS SIGN} 95 % CI | Range | n |"
    )
    assert lines[6] == (
        "| `selftest.sleep[ms=50]` | wall | 50.21 ms \N{PLUS-MINUS SIGN} 0.4 % |"
        " 50.08 ms \N{HORIZONTAL ELLIPSIS} 50.61 ms | 10 |"
    )
    assert lines[7] == "| `selftest.fail` |  | failed | RuntimeError: boom |  |"
