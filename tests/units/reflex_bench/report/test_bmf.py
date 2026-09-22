"""Tests for reflex_bench.report.bmf."""

from __future__ import annotations

import json

import pytest
from reflex_bench.registry import Metric
from reflex_bench.report.bmf import to_bmf

from tests.units.reflex_bench.factories import WALL, make_doc, make_entry

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


def test_bencher_metric_format():
    doc = make_doc([
        make_entry("selftest.sleep", {"wall": (WALL, SLEEP)}, params={"ms": 50}),
        make_entry(
            "selftest.exact",
            {"bytes": (Metric(unit="B", direction="lower", assume="exact"), [238_400])},
        ),
        make_entry("selftest.short", {"wall": (WALL, [1.0, 2.0])}),
        make_entry(
            "selftest.fail", {"wall": (WALL, [])}, status="failed", error="boom"
        ),
    ])
    exported = to_bmf(doc)
    assert exported == {
        "selftest.sleep[ms=50]": {
            "wall": {
                "value": pytest.approx(0.05021),
                "lower_value": 0.05015,
                "upper_value": 0.0504,
            }
        },
        "selftest.exact": {"bytes": {"value": 238_400.0}},
        "selftest.short": {"wall": {"value": 1.5}},
    }
    json.dumps(exported, allow_nan=False)
