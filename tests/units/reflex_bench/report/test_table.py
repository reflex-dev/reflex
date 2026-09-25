"""Tests for reflex_bench.report.table."""

from __future__ import annotations

import io

import pytest
from reflex_bench import compare
from reflex_bench.registry import Metric
from reflex_bench.report import table
from reflex_bench.scheduler import Policy
from reflex_bench.schema import ResultDoc

from tests.units.reflex_bench.factories import WALL, make_doc, make_entry, make_machine

EXACT = Metric(unit="B", direction="lower", assume="exact")
# Median 50.21 ms, range 50.08 to 50.61 ms, 95 % CI [50.15, 50.40] ms.
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
# 30 values around 1 s; the one at index 7 is a severe outlier.
NOISE = [0.96 + 0.003 * i for i in range(30)]
NOISE[7] = 1.4


def _render(render, *args) -> str:
    buffer = io.StringIO()
    render(table.make_console(plain=True, file=buffer, width=100), *args)
    return buffer.getvalue()


@pytest.fixture
def doc() -> ResultDoc:
    return make_doc([
        make_entry(
            "selftest.sleep",
            {"wall": (WALL, [0.07, *SLEEP])},
            params={"ms": 50},
            warmup=1,
        ),
        make_entry("selftest.noise", {"value": (WALL, NOISE)}, params={"cv": 5}),
        make_entry("selftest.exact", {"bytes": (EXACT, [238_400])}),
        make_entry(
            "selftest.fail",
            {"wall": (WALL, [])},
            status="failed",
            error="RuntimeError: boom",
        ),
    ])


def test_header_matches_the_report_layout(doc: ResultDoc):
    lines = _render(table.render_header, doc, 2).splitlines()
    assert lines[0] == (
        "reflex-bench 0.1.0 \N{MIDDLE DOT} reflex 0.9.12 (workspace 258d66c, dirty)"
        " \N{MIDDLE DOT} py 3.12.8"
    )
    assert lines[1] == (
        "machine: linux-x86_64 \N{MIDDLE DOT} AMD Ryzen 9 7950X \N{MIDDLE DOT} 32 cores"
        " \N{MIDDLE DOT} governor=powersave \N{WARNING SIGN} \N{MIDDLE DOT} turbo=on"
        " \N{WARNING SIGN} \N{MIDDLE DOT} load 0.4"
    )
    assert lines[2] == (
        "policy: runs 10\N{EN DASH}30, min-time 30 s, warmup per benchmark, timeout per"
        " benchmark, \N{GREEK SMALL LETTER ALPHA}=0.01 (Holm), threshold 3 %, CI 95 %,"
        " bootstrap 10000, seed 1234, fail-on never"
    )
    assert lines[3] == (
        "\N{WARNING SIGN} 2 doctor warnings: expect \N{PLUS-MINUS SIGN}3\N{EN DASH}5 % extra"
        " variance (run `reflex-bench doctor`)"
    )


def test_policy_line_variants():
    fixed = Policy(runs=3, warmup=0, timeout_s=5).to_doc()
    assert table.policy_line(fixed, 1).startswith(
        "policy: runs 3 (fixed), warmup 0, timeout 5 s,"
    )
    smoke = Policy(smoke=True).to_doc()
    assert table.policy_line(smoke, 1).startswith(
        "policy: smoke (1 run, no warmup, no statistics)"
    )


def test_machine_line_flags_vms_battery_and_load():
    line = table.machine_line(
        make_machine(
            governor=None, turbo=None, virtualized=True, ac_power=False, load_avg_1m=2.5
        )
    )
    assert line.endswith(
        "32 cores \N{MIDDLE DOT} vm \N{WARNING SIGN} \N{MIDDLE DOT} battery \N{WARNING SIGN}"
        " \N{MIDDLE DOT} load 2.5 \N{WARNING SIGN}"
    )


def test_run_table(doc: ResultDoc):
    lines = _render(table.render_run, doc).splitlines()
    assert lines[0].split() == [
        "selftest.sleep[ms=50]",
        "median",
        "\N{PLUS-MINUS SIGN}",
        "95",
        "%",
        "CI",
        "range",
        "n",
    ]
    assert lines[1].split() == [
        "wall",
        "50.21",
        "ms",
        "\N{PLUS-MINUS SIGN}",
        "0.4",
        "%",
        "50.08",
        "ms",
        "\N{HORIZONTAL ELLIPSIS}",
        "50.61",
        "ms",
        "10",
    ]
    text = "\n".join(lines)
    assert "\N{WARNING SIGN} 1 severe outlier (sample 7: +" in text
    assert "%). Kept." in text
    assert "238.4 kB (exact)" in text
    assert "  \N{BALLOT X} failed: RuntimeError: boom" in text
    assert lines[-1] == "4 benchmarks: 3 ok \N{MIDDLE DOT} 1 failed"


def test_run_table_columns_are_aligned(doc: ResultDoc):
    lines = _render(table.render_run, doc).splitlines()
    header, wall = lines[0], lines[1]
    assert header.index("median") == wall.index("50.21")
    assert header.index("range") == wall.index("50.08")
    assert header.rindex("n") == wall.rindex("10") + 1


def test_run_table_without_enough_samples_for_a_ci():
    doc = make_doc([
        make_entry("selftest.sleep", {"wall": (WALL, [0.01, 0.011, 0.012])})
    ])
    assert "11.00 ms (need \N{GREATER-THAN OR EQUAL TO} 6 samples)" in _render(
        table.render_run, doc
    )


def test_smoke_table_shows_single_values():
    doc = make_doc(
        [make_entry("selftest.sleep", {"wall": (WALL, [0.0123])}, status="ok")],
        policy=Policy(smoke=True),
    )
    doc["benchmarks"][0]["metrics"]["wall"]["summary"] = {}
    assert "12.30 ms (smoke)" in _render(table.render_run, doc)


def test_unsupported_entries():
    doc = make_doc([
        make_entry(
            "selftest.new",
            {"wall": (WALL, [])},
            status="unsupported",
            error="requires reflex >= 9.0",
        )
    ])
    assert "  \N{EN DASH} unsupported: requires reflex >= 9.0" in _render(
        table.render_run, doc
    )


def test_status_summary_is_pluralized():
    one = make_doc([make_entry("selftest.fail", {"wall": (WALL, [])}, status="failed")])
    assert "1 benchmark: 1 failed" in _render(table.render_run, one)
    two = make_doc([
        make_entry("selftest.fail", {"wall": (WALL, [])}, status="failed"),
        make_entry("selftest.sleep", {"wall": (WALL, SLEEP)}),
    ])
    assert "2 benchmarks: 1 failed" in _render(table.render_run, two)


def _compared() -> ResultDoc:
    base = make_doc(
        [
            make_entry("selftest.sleep", {"wall": (WALL, SLEEP)}, params={"ms": 50}),
            make_entry("selftest.exact", {"bytes": (EXACT, [238_400])}),
        ],
        invocation_id="base",
    )
    head = make_doc(
        [
            make_entry(
                "selftest.sleep",
                {"wall": (WALL, [v * 1.054 for v in SLEEP])},
                params={"ms": 50},
            ),
            make_entry("selftest.exact", {"bytes": (EXACT, [241_000])}),
            make_entry("selftest.new", {"wall": (WALL, SLEEP)}),
        ],
        invocation_id="head",
    )
    compare.compare(
        base,
        head,
        threshold=0.03,
        alpha=0.01,
        resamples=2000,
        seed=1,
        base_label="base.json",
        head_label="head.json",
    )
    return head


def test_comparison_table():
    lines = _render(table.render_comparison, _compared()).splitlines()
    assert lines[0] == (
        "reflex-bench compare base.json head.json   \N{GREEK SMALL LETTER ALPHA}=0.01"
        " (Holm, 1 metric)  threshold=3 %"
    )
    assert lines[2].split() == ["base", "head"]
    sleep = lines[3]
    assert sleep.split()[:6] == [
        "selftest.sleep[ms=50]",
        "wall",
        "50.21",
        "ms",
        "\N{PLUS-MINUS SIGN}",
        "0.4",
    ]
    assert "52.92 ms" in sleep
    assert "+5.4 % [" in sleep
    assert "n=10/10" in sleep
    assert sleep.endswith("regressed")
    exact = lines[4]
    assert exact.split()[:4] == ["selftest.exact", "bytes", "238.4", "kB"]
    assert "+1.1 %" in exact
    assert "exact" in exact
    assert exact.endswith("~ below threshold")
    assert lines[5].startswith(
        "geomean (time) +5.4 % \N{MIDDLE DOT} geomean (bytes) +1.1 %"
    )
    assert lines[6] == (
        "1 regressed \N{MIDDLE DOT} 0 improved \N{MIDDLE DOT} 0 inconclusive"
        " \N{MIDDLE DOT} 1 unchanged"
    )
    assert lines[7] == "only in head: selftest.new"


def test_comparison_of_an_unannotated_document_prints_nothing(doc: ResultDoc):
    assert _render(table.render_comparison, doc) == ""


def test_samples_listing(doc: ResultDoc):
    text = _render(table.render_samples, doc)
    assert "selftest.sleep[ms=50] \N{MIDDLE DOT} wall [A]" in text
    assert "     0  70.00 ms  warmup" in text
    assert "     1  50.08 ms" in text
