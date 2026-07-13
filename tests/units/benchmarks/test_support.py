"""Tests for shared performance benchmark support."""

import json

import pytest

from tests.benchmarks.support.pipeline_trace import PipelineTrace, StageEvent
from tests.benchmarks.support.report import (
    BenchmarkEnvironment,
    BenchmarkResult,
    PerformanceReport,
    percentile,
)


def test_percentile_interpolates_and_validates():
    """Percentiles interpolate and reject values outside the valid range."""
    assert percentile([], 50) == 0
    assert percentile([1, 2, 3, 4, 5], 95) == pytest.approx(4.8)
    with pytest.raises(ValueError, match="between 0 and 100"):
        percentile([1], 101)


def test_performance_report_round_trip(tmp_path):
    """Reports retain observations, summaries, metrics, and environment data."""
    environment = BenchmarkEnvironment(
        commit="abc",
        branch="branch",
        python="3.14",
        implementation="CPython",
        operating_system="test",
        machine="machine",
        processor="processor",
        cpu_count=4,
        ci=True,
    )
    report = PerformanceReport("event-loop", environment=environment)
    report.add(
        BenchmarkResult(
            name="warm-event",
            parameters={"tokens": 1},
            observations_ms=[1, 2, 3],
            metrics={"peak_tasks": 4},
            warmup_iterations=1,
            measurement_iterations=3,
        )
    )

    output = report.write(tmp_path / "report.json")
    payload = json.loads(output.read_text())

    assert payload["schema_version"] == 1
    assert payload["environment"]["commit"] == "abc"
    assert payload["results"][0]["summary"]["p50_ms"] == 2
    assert payload["results"][0]["metrics"]["peak_tasks"] == 4


def test_pipeline_trace_durations_and_chrome_output(tmp_path):
    """Pipeline traces calculate durations and produce Chrome trace events."""
    trace = PipelineTrace()
    trace.extend([
        StageEvent("token", "enqueued", 1_000_000),
        StageEvent("token", "dequeued", 2_500_000),
    ])

    assert trace.durations_ms([("enqueued", "dequeued")]) == {
        "enqueued_to_dequeued": [1.5]
    }
    path = trace.write_chrome_trace(tmp_path / "trace.json")
    payload = json.loads(path.read_text())
    assert [event["name"] for event in payload["traceEvents"]] == [
        "enqueued",
        "dequeued",
    ]
