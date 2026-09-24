"""Tests for reflex_bench.compare."""

from __future__ import annotations

import copy
import random
from typing import Any

import pytest
from reflex_bench import compare
from reflex_bench.registry import Metric
from reflex_bench.schema import ResultDoc, validate
from reflex_bench.suites.selftest import noise_value

from .factories import WALL, make_ab_entry, make_doc, make_entry, make_machine

EXACT = Metric(unit="B", direction="lower", assume="exact")


def _noise(seed: int, n: int, cv: float, shift: float = 1.0) -> list[float]:
    rng = random.Random(seed)
    return [noise_value(rng, cv, shift) for _ in range(n)]


def _docs(
    shift: float = 1.0, n: int = 30, head_bytes: float = 241_000
) -> tuple[ResultDoc, ResultDoc]:
    base = make_doc(
        [
            make_entry(
                "selftest.noise",
                {"value": (WALL, _noise(1, n, cv=2))},
                params={"cv": 2},
            ),
            make_entry("selftest.exact", {"bytes": (EXACT, [238_400])}),
        ],
        invocation_id="base-id",
    )
    head = make_doc(
        [
            make_entry(
                "selftest.noise",
                {"value": (WALL, _noise(2, n, cv=2, shift=shift))},
                params={"cv": 2},
            ),
            make_entry("selftest.exact", {"bytes": (EXACT, [head_bytes])}),
        ],
        invocation_id="head-id",
    )
    return base, head


def _compare(base: ResultDoc, head: ResultDoc, **kwargs) -> None:
    compare.compare(
        base, head, threshold=0.03, alpha=0.01, resamples=2000, seed=7, **kwargs
    )


def _verdicts(doc: ResultDoc) -> dict[str, str]:
    return {
        f"{row.name}:{row.metric}": row.comparison["verdict"]
        for row in compare.rows(doc)
    }


def test_regression_is_detected_and_head_is_annotated():
    base, head = _docs(shift=1.10)
    _compare(base, head, base_label="base.json", head_label="head.json")
    assert _verdicts(head) == {
        "selftest.noise[cv=2]:value": "regressed",
        "selftest.exact:bytes": "unchanged",
    }
    comparison = head["benchmarks"][0]["metrics"]["value"]["comparison"]
    assert comparison is not None
    assert comparison["base"]["invocation_id"] == "base-id"
    assert comparison["head"]["invocation_id"] == "head-id"
    assert (comparison["base"]["n"], comparison["head"]["n"]) == (30, 30)
    assert comparison["test"] == "mwu-exact" or comparison["test"] == "mwu-normal"
    assert comparison["ratio"] == pytest.approx(0.10, abs=0.02)
    assert comparison["p_adj"] is not None
    assert comparison["runs_needed"] is None
    compared_to = head.get("compared_to")
    assert compared_to is not None
    assert compared_to["family_size"] == 1
    assert compared_to["base_label"] == "base.json"
    assert validate(head) == []


def test_unchanged_and_exact_regression():
    base, head = _docs(shift=1.0, head_bytes=260_000)
    _compare(base, head)
    assert _verdicts(head) == {
        "selftest.noise[cv=2]:value": "unchanged",
        "selftest.exact:bytes": "regressed",
    }
    assert compare.verdict_counts(head) == {"unchanged": 1, "regressed": 1}


def test_too_few_samples_are_inconclusive_with_an_estimate():
    base, head = _docs(n=3)
    _compare(base, head)
    comparison = head["benchmarks"][0]["metrics"]["value"]["comparison"]
    assert comparison is not None
    assert comparison["verdict"] == "inconclusive"
    assert comparison["ci"] is None
    assert comparison["runs_needed"] == 6


def test_different_profiles_are_not_compared_unless_forced():
    base, head = _docs(shift=1.10)
    head["machine"] = make_machine("graviton-arm64")
    _compare(base, head)
    assert compare.rows(head) == []
    compared_to = head.get("compared_to")
    assert compared_to is not None
    assert [item["id"] for item in compared_to["not_comparable"]] == [
        "selftest.noise[cv=2]",
        "selftest.exact",
    ]
    assert compared_to["not_comparable"][0]["reasons"] == [
        "machine profile differs: test-profile vs graviton-arm64"
    ]
    _compare(base, head, force=True)
    assert _verdicts(head)["selftest.noise[cv=2]:value"] == "regressed"
    assert head.get("compared_to", {}).get("forced") is True


def test_an_edited_fixture_is_reported_not_compared_unless_forced():
    base, head = _docs(shift=1.10)
    for doc, digit in ((base, "a"), (head, "b")):
        doc["benchmarks"][0]["dims"] = {"fixture": "playground"}
        doc["benchmarks"][0]["fixture_hash"] = "sha256:" + digit * 64
    _compare(base, head)
    compared_to = head.get("compared_to")
    assert compared_to is not None
    assert compared_to["only_in_base"] == compared_to["only_in_head"] == []
    assert compared_to["not_comparable"] == [
        {
            "id": "selftest.noise[cv=2]",
            "reasons": [
                "fixture content hash differs: sha256:aaaaaaaaaaaa vs sha256:bbbbbbbbbbbb"
            ],
        }
    ]
    _compare(base, head, force=True)
    assert _verdicts(head)["selftest.noise[cv=2]:value"] == "regressed"


def test_failed_entries_and_entries_on_one_side():
    base, head = _docs()
    base["benchmarks"][0]["status"] = "failed"
    head["benchmarks"][0]["status"] = "timeout"
    head["benchmarks"].append(make_entry("selftest.new", {"wall": (WALL, [1.0])}))
    base["benchmarks"].append(make_entry("selftest.gone", {"wall": (WALL, [1.0])}))
    _compare(base, head)
    compared_to = head.get("compared_to")
    assert compared_to is not None
    assert compared_to["only_in_base"] == ["selftest.gone"]
    assert compared_to["only_in_head"] == ["selftest.new"]
    assert compared_to["not_comparable"] == [
        {
            "id": "selftest.noise[cv=2]",
            "reasons": ["base status is failed", "head status is timeout"],
        }
    ]
    assert compare.failed_in_head(head) == []


def test_failing_in_head_is_a_regression():
    base, head = _docs()
    head["benchmarks"][0].update(status="failed", error="boom")
    head["benchmarks"][1]["status"] = "unsupported"
    head["benchmarks"].append(
        make_entry("selftest.new", {"wall": (WALL, [])}, status="timeout")
    )
    _compare(base, head)
    compared_to = head.get("compared_to")
    assert compared_to is not None
    assert compare.failed_in_head(head) == [
        {
            "id": "selftest.noise[cv=2]",
            "status": "failed",
            "base_status": "ok",
            "error": "boom",
        },
        {
            "id": "selftest.new",
            "status": "timeout",
            "base_status": None,
            "error": None,
        },
    ]
    # Becoming unsupported is not a failure.
    assert compared_to["not_comparable"] == [
        {"id": "selftest.exact", "reasons": ["head status is unsupported"]}
    ]
    assert validate(head) == []


def test_missing_metric_and_missing_samples_are_not_comparable():
    base, head = _docs()
    renamed = copy.deepcopy(head)
    renamed["benchmarks"][1]["metrics"]["size"] = renamed["benchmarks"][1][
        "metrics"
    ].pop("bytes")
    _compare(base, renamed, force=True)
    compared_to = renamed.get("compared_to")
    assert compared_to is not None
    assert compared_to["not_comparable"] == [
        {
            "id": "selftest.exact",
            "reasons": [
                "metric 'size' is missing in base",
                "metric 'bytes' is missing in head",
            ],
        }
    ]


def test_holm_runs_across_all_tested_metrics():
    base, head = _docs(shift=1.10)
    base["benchmarks"].append(
        make_entry("selftest.other", {"value": (WALL, _noise(3, 30, cv=2))})
    )
    head["benchmarks"].append(
        make_entry("selftest.other", {"value": (WALL, _noise(4, 30, cv=2))})
    )
    _compare(base, head)
    compared_to = head.get("compared_to")
    assert compared_to is not None
    assert compared_to["family_size"] == 2
    rows = {row.name: row.comparison for row in compare.rows(head)}
    raw = rows["selftest.noise[cv=2]"]
    assert raw["p"] is not None
    assert raw["p_adj"] is not None
    assert raw["p_adj"] >= raw["p"]


def test_comparisons_are_reproducible_and_replaced():
    base, head = _docs(shift=1.10)
    _compare(base, head)
    first = copy.deepcopy(head)
    _compare(base, head)
    assert head == first
    _compare(base, head, force=True)
    assert head.get("compared_to", {}).get("forced") is True


def test_zero_base_gives_no_ratio():
    base = make_doc([make_entry("selftest.exact", {"bytes": (EXACT, [0])})])
    head = make_doc([make_entry("selftest.exact", {"bytes": (EXACT, [10])})])
    _compare(base, head)
    (row,) = compare.rows(head)
    assert row.comparison["ratio"] is None
    assert row.comparison["verdict"] == "regressed"
    assert validate(head) == []


def test_zero_base_median_is_compared_absolutely():
    base = make_doc([make_entry("selftest.zero", {"value": (WALL, [0.0] * 10)})])
    head = make_doc([make_entry("selftest.zero", {"value": (WALL, [5.0] * 10)})])
    _compare(base, head)
    (row,) = compare.rows(head)
    assert row.comparison.get("mode") == "absolute"
    assert row.comparison["ratio"] is None
    assert row.comparison["ci"] == [5.0, 5.0]
    assert row.comparison["verdict"] == "regressed"
    assert validate(head) == []


def test_zero_in_the_base_keeps_the_ratio():
    a = [0.0] + [1.0 + 0.001 * i for i in range(29)]
    b = [2.0 + 0.001 * i for i in range(30)]
    base = make_doc([make_entry("selftest.zero", {"value": (WALL, a)})])
    head = make_doc([make_entry("selftest.zero", {"value": (WALL, b)})])
    _compare(base, head)
    (row,) = compare.rows(head)
    assert row.comparison.get("mode") == "ratio"
    assert row.comparison["ratio"] == pytest.approx(0.988, abs=0.001)
    assert row.comparison["verdict"] == "regressed"
    assert row.comparison["runs_needed"] is None


def test_geomeans_per_unit_family():
    base, head = _docs(shift=1.10)
    _compare(base, head)
    means = compare.geomeans(head)
    assert list(means) == ["time", "bytes"]
    assert means["bytes"] == pytest.approx(241_000 / 238_400 - 1)


def _ab_doc(shift: float = 1.0, **entry: Any) -> ResultDoc:
    samples = {"A": _noise(1, 30, cv=2), "B": _noise(2, 30, cv=2, shift=shift)}
    return make_doc(
        [make_ab_entry("selftest.noise", {"value": (WALL, samples)}, **entry)],
        arms=("A", "B"),
    )


def test_comparing_the_arms_of_one_document():
    doc = _ab_doc(shift=1.10)
    _compare(doc, doc, base_arm="A", head_arm="B")
    (row,) = compare.rows(doc)
    assert row.comparison["verdict"] == "regressed"
    assert (row.comparison["base"]["arm"], row.comparison["head"]["arm"]) == ("A", "B")
    assert (row.comparison["base"]["n"], row.comparison["head"]["n"]) == (30, 30)
    compared_to = doc.get("compared_to")
    assert compared_to is not None
    assert compared_to["only_in_base"] == compared_to["only_in_head"] == []
    assert compared_to["not_comparable"] == []
    assert validate(doc) == []
    _compare(doc, doc, base_arm="A", head_arm="A")
    assert _verdicts(doc) == {"selftest.noise:value": "unchanged"}


def test_a_failure_in_one_arm_of_one_document():
    head = _ab_doc(status="failed", error="boom", failed_arms=["B"])
    _compare(head, head, base_arm="A", head_arm="B")
    assert compare.failed_in_head(head) == [
        {
            "id": "selftest.noise",
            "status": "failed",
            "base_status": "ok",
            "error": "boom",
        }
    ]
    base = _ab_doc(status="failed", error="boom", failed_arms=["A"])
    _compare(base, base, base_arm="A", head_arm="B")
    compared_to = base.get("compared_to")
    assert compared_to is not None
    assert compare.failed_in_head(base) == []
    assert compared_to["not_comparable"] == [
        {"id": "selftest.noise", "reasons": ["base status is failed"]}
    ]
    # Without failed_arms (documents of single-arm runs) a failure fails every arm.
    both = _ab_doc(status="failed", error="boom")
    _compare(both, both, base_arm="A", head_arm="B")
    compared_to = both.get("compared_to")
    assert compared_to is not None
    assert compared_to["not_comparable"] == [
        {
            "id": "selftest.noise",
            "reasons": ["base status is failed", "head status is failed"],
        }
    ]
