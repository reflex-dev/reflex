"""Tests for reflex_bench.noise."""

from __future__ import annotations

from collections.abc import Sequence

import pytest
from reflex_bench import noise
from reflex_bench.schema import ResultDoc

from .factories import make_run

OTHER_VERSION = "sha256:" + "1" * 64
WARM = "lifecycle.compile.warm[app=playground]"


def rows_of(
    docs: Sequence[ResultDoc], **options
) -> dict[tuple[str, str], noise.NoiseRow]:
    """Compute the noise rows of documents, keyed by instance name and metric.

    Args:
        docs: The documents.
        **options: Passed to :func:`noise.series`.

    Returns:
        The rows; fails when two rows share a name and metric.
    """
    rows = noise.series(docs, **options)
    keyed = {(row.name, row.metric): row for row in rows}
    assert len(keyed) == len(rows)
    return keyed


def test_robust_cv_and_medians_match_hand_computed_values():
    medians = [1.0, 1.1, 0.9, 1.0, 1.2]
    row = rows_of([make_run(m, day=i + 1) for i, m in enumerate(medians)])[WARM, "wall"]
    assert row.runs == 5
    assert row.median == pytest.approx(1.0)
    # MAD of the run medians is 0.1 around the median 1.0.
    assert row.between_cv == pytest.approx(1.4826 * 0.1)
    assert row.within_cv == pytest.approx(0.01)
    assert (row.unit, row.direction, row.assume) == ("s", "lower", "nothing")


def test_max_step_follows_the_start_time_not_the_file_order():
    docs = [make_run(2.0, day=3), make_run(1.0, day=1), make_run(1.0, day=2)]
    assert rows_of(docs)[WARM, "wall"].max_step == pytest.approx(1.0)


def test_a_single_run_has_no_spread_between_runs():
    row = rows_of([make_run(1.0, day=1)])[WARM, "wall"]
    assert (row.runs, row.between_cv, row.max_step) == (1, None, None)


@pytest.mark.parametrize(
    "other",
    [
        {"profile_id": "other-profile"},
        {"version": OTHER_VERSION},
        {"fixture_hash": "sha256:" + "2" * 64},
    ],
)
def test_series_never_pool_across_series_keys(other):
    rows = noise.series([make_run(1.0, day=1), make_run(5.0, day=2, **other)])
    walls = [row for row in rows if row.metric == "wall"]
    assert [row.runs for row in walls] == [1, 1]
    assert {row.median for row in walls} == {1.0, 5.0}
    assert len({row.series for row in walls}) == 2


def test_other_kinds_interrupted_runs_and_failed_entries_are_skipped():
    docs = [
        make_run(1.0, day=1),
        make_run(9.0, day=2, kind="pr"),
        make_run(9.0, day=3, interrupted=True),
        make_run(9.0, day=4, status="failed"),
    ]
    assert rows_of(docs)[WARM, "wall"].runs == 1
    assert rows_of(docs, kind="pr")[WARM, "wall"].median == pytest.approx(9.0)


@pytest.mark.parametrize(
    ("medians", "min_runs", "threshold", "expected"),
    [
        ([1.0, 1.0, 1.0, 1.0, 1.0], 5, 0.03, "gate-candidate"),
        ([1.0, 1.02, 0.98, 1.0, 1.02], 5, 0.09, "gate-candidate"),
        ([1.0, 1.1, 0.9, 1.0, 1.2], 5, 0.45, "track"),
        ([1.0, 1.0, 1.0, 1.0], 5, None, "noisy"),
    ],
)
def test_classes(medians, min_runs, threshold, expected):
    docs = [make_run(m, day=i + 1) for i, m in enumerate(medians)]
    row = rows_of(docs, min_runs=min_runs)[WARM, "wall"]
    assert row.threshold == (None if threshold is None else pytest.approx(threshold))
    assert row.cls == expected


def test_exact_metrics_are_classed_exact():
    row = rows_of([make_run(1.0, day=1)], min_runs=5)[WARM, "bytes"]
    assert (row.cls, row.threshold, row.assume) == ("exact", None, "exact")


def test_threshold_rounds_up_to_a_whole_percent():
    assert noise.threshold(0.0) == pytest.approx(0.03)
    assert noise.threshold(0.01) == pytest.approx(0.03)
    assert noise.threshold(0.0101) == pytest.approx(0.04)
    assert noise.threshold(1 / 30) == pytest.approx(0.10)


def test_rows_are_sorted_by_name_and_metric():
    rows = noise.series([make_run(1.0, day=1)])
    assert [(row.name, row.metric) for row in rows] == [
        (WARM, "bytes"),
        (WARM, "wall"),
    ]
