"""Tests for shared performance benchmark support."""

import asyncio
import json
from types import SimpleNamespace

import pytest

from tests.benchmarks.support.apps import lifecycle_app_source
from tests.benchmarks.support.diagnostics import capture_async_diagnostics
from tests.benchmarks.support.pipeline_trace import PipelineTrace, StageEvent
from tests.benchmarks.support.report import (
    BenchmarkEnvironment,
    BenchmarkResult,
    PerformanceReport,
    percentile,
)
from tests.benchmarks.support.socket_client import run_clients


def test_percentile_interpolates_and_validates():
    """Percentiles interpolate and reject values outside the valid range."""
    assert percentile([], 50) == 0
    assert percentile([1, 2, 3, 4, 5], 95) == pytest.approx(4.8)
    with pytest.raises(ValueError, match="between 0 and 100"):
        percentile([1], 101)


def test_payload_kind_uses_python_310_compatible_enum_base():
    """Payload enums avoid bases that were added after Python 3.10."""
    pytest.importorskip("pydantic")
    from tests.benchmarks.support.events import PayloadKind

    assert not any(
        base.__module__ == "enum" and base.__name__ == "StrEnum"
        for base in PayloadKind.__mro__
    )


def test_production_harness_is_module_scoped():
    """The in-process production harness stops before unrelated modules run."""
    pytest.importorskip("pydantic")
    from tests.performance import conftest as performance_conftest

    fixture = performance_conftest.performance_load_app
    marker = fixture._fixture_function_marker  # pyright: ignore[reportPrivateUsage]
    assert marker.scope == "module"


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
    assert [
        event["name"] for event in payload["traceEvents"] if event["ph"] == "i"
    ] == ["enqueued", "dequeued"]


def test_pipeline_trace_chrome_tids_are_integers():
    """Chrome traces emit integer pids/tids and name tokens via metadata."""
    trace = PipelineTrace()
    trace.extend([
        StageEvent("token-a", "enqueued", 1_000_000),
        StageEvent("token-b", "enqueued", 2_000_000),
        StageEvent("token-a", "dequeued", 3_000_000),
    ])

    payload = trace.chrome_trace()
    assert all(
        isinstance(event["pid"], int) and isinstance(event["tid"], int)
        for event in payload["traceEvents"]
    )
    instants = [event for event in payload["traceEvents"] if event["ph"] == "i"]
    assert instants[0]["tid"] == instants[2]["tid"]
    assert instants[0]["tid"] != instants[1]["tid"]
    thread_names = {
        event["tid"]: event["args"]["name"]
        for event in payload["traceEvents"]
        if event.get("name") == "thread_name" and event["ph"] == "M"
    }
    assert thread_names[instants[0]["tid"]] == "token-a"
    assert thread_names[instants[1]["tid"]] == "token-b"


def test_pipeline_trace_preserves_repeated_stage_pairs():
    """Repeated streaming stages produce one duration per occurrence."""
    trace = PipelineTrace()
    trace.extend([
        StageEvent("token", "delta_started", 1_000_000),
        StageEvent("token", "delta_finished", 2_000_000),
        StageEvent("token", "delta_started", 3_000_000),
        StageEvent("token", "delta_finished", 5_000_000),
    ])

    assert trace.durations_ms([("delta_started", "delta_finished")]) == {
        "delta_started_to_delta_finished": [1.0, 2.0]
    }


@pytest.mark.asyncio
async def test_run_clients_leaves_default_executor_usable():
    """The load helper does not close the event loop's default executor."""
    results = await run_clients(
        2,
        lambda index, executor: asyncio.get_running_loop().run_in_executor(
            executor, lambda: index
        ),
    )

    assert results == [0, 1]
    assert await asyncio.to_thread(lambda: "still-usable") == "still-usable"


class _FakeRedis:
    """Minimal async Redis stand-in recording lifecycle calls."""

    def __init__(self, calls: list[str], dbsize: int = 0):
        """Initialize the fake.

        Args:
            calls: Shared call log appended to by every method.
            dbsize: Key count reported by ``dbsize``.
        """
        self.calls = calls
        self._dbsize = dbsize

    async def ping(self) -> bool:
        """Record and acknowledge a ping.

        Returns:
            Always True.
        """
        self.calls.append("ping")
        return True

    async def dbsize(self) -> int:
        """Record and report the configured key count.

        Returns:
            The configured key count.
        """
        self.calls.append("dbsize")
        return self._dbsize

    async def flushdb(self) -> None:
        """Record a database flush."""
        self.calls.append("flushdb")

    async def aclose(self) -> None:
        """Record closing the connection pool."""
        self.calls.append("aclose")


def test_performance_redis_url_requires_database_index(monkeypatch):
    """URLs without an explicit database index are rejected."""
    pytest.importorskip("redis")
    from tests.benchmarks.support import redis as redis_support

    monkeypatch.setenv(redis_support.REDIS_URL_ENV, "redis://127.0.0.1:6379")
    with pytest.raises(ValueError, match="database index"):
        redis_support.performance_redis_url()

    monkeypatch.setenv(redis_support.REDIS_URL_ENV, "redis://127.0.0.1:6379/15")
    assert redis_support.performance_redis_url() == "redis://127.0.0.1:6379/15"


async def test_real_redis_state_manager_refuses_nonempty_database(monkeypatch):
    """A database that already holds keys is never flushed."""
    pytest.importorskip("redis")
    from tests.benchmarks.support import redis as redis_support

    calls: list[str] = []
    fake = _FakeRedis(calls, dbsize=3)
    monkeypatch.setenv(redis_support.REDIS_URL_ENV, "redis://127.0.0.1:6379/15")
    monkeypatch.setattr(
        redis_support, "Redis", SimpleNamespace(from_url=lambda url: fake)
    )

    with pytest.raises(RuntimeError, match="not empty"):
        async with redis_support.real_redis_state_manager():
            pass

    assert "flushdb" not in calls
    assert calls[-1] == "aclose"


async def test_real_redis_state_manager_cleanup_survives_close_failure(monkeypatch):
    """The manager closes before the flush, which runs despite a close failure."""
    pytest.importorskip("redis")
    from tests.benchmarks.support import redis as redis_support

    calls: list[str] = []
    fake = _FakeRedis(calls)
    monkeypatch.setenv(redis_support.REDIS_URL_ENV, "redis://127.0.0.1:6379/15")
    monkeypatch.setattr(
        redis_support, "Redis", SimpleNamespace(from_url=lambda url: fake)
    )

    class _FailingManager:
        """State-manager stand-in whose close always fails."""

        def __init__(self, redis):
            """Store the redis client.

            Args:
                redis: The fake redis client.
            """
            self.redis = redis

        async def close(self) -> None:
            """Record the close attempt and fail.

            Raises:
                RuntimeError: Always, to exercise cleanup ordering.
            """
            calls.append("close")
            msg = "close failed"
            raise RuntimeError(msg)

    monkeypatch.setattr(redis_support, "StateManagerRedis", _FailingManager)

    with pytest.raises(RuntimeError, match="close failed"):
        async with redis_support.real_redis_state_manager():
            pass

    # The manager is closed first so any oplock lease write-backs land before
    # the flush; the flush then runs on a fresh client even though close()
    # raised, and both the fresh client and the original connection are closed.
    assert calls == ["ping", "dbsize", "close", "flushdb", "aclose", "aclose"]


async def test_capture_async_diagnostics_formats_each_frame_once(tmp_path):
    """Task stacks include each ancestor frame once instead of once per frame."""
    task = asyncio.current_task()
    assert task is not None
    task.set_name("diagnostics-under-test")
    await asyncio.sleep(0)

    destination = capture_async_diagnostics(tmp_path / "diagnostics.json")
    payload = json.loads(destination.read_text())
    stack = "".join(
        line
        for task_info in payload["tasks"]
        if task_info["name"] == "diagnostics-under-test"
        for line in task_info["stack"]
    )
    assert ", in test_capture_async_diagnostics_formats_each_frame_once" in stack
    assert stack.count(", in <module>") == 1


def test_lifecycle_app_source_uses_public_api_transformer():
    """Generated app sources register extra routes via the public seam."""
    source = lifecycle_app_source(rows=1, pages=1)
    assert "_api" not in source
    assert "api_transformer" in source


def test_baseline_server_startup_failure_surfaces_thread_exception(monkeypatch):
    """A server thread crash is reported instead of a bare startup timeout."""
    pytest.importorskip("socketio")
    uvicorn = pytest.importorskip("uvicorn")
    from tests.benchmarks.support.baseline_server import BaselineSocketServer

    def crash(self) -> None:
        """Simulate an immediate server crash.

        Args:
            self: The uvicorn server.

        Raises:
            RuntimeError: Always.
        """
        msg = "boom during startup"
        raise RuntimeError(msg)

    monkeypatch.setattr(uvicorn.Server, "run", crash)
    with (
        pytest.raises(TimeoutError, match="boom during startup"),
        BaselineSocketServer(response={}),
    ):
        pass
