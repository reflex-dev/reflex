"""Production Socket.IO concurrency, throughput, and tail-latency benchmarks."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Generator
from pathlib import Path

import pytest
from reflex_base.config import get_config
from reflex_base.registry import RegistrationContext

from reflex.testing import AppHarness, AppHarnessProd
from tests.benchmarks.support import BenchmarkResult, PerformanceReport
from tests.benchmarks.support.apps import load_app_source
from tests.benchmarks.support.socket_client import run_clients, run_socket_client


@pytest.fixture(scope="module")
def performance_load_app(tmp_path_factory) -> Generator[AppHarness, None, None]:
    """Build and run the representative production load application.

    Args:
        tmp_path_factory: Pytest temporary directory factory.

    Yields:
        Running production app harness.
    """
    with AppHarnessProd.create(
        root=tmp_path_factory.mktemp("performance_load"),
        app_source=load_app_source(),
        app_name="performance_load",
    ) as harness:
        yield harness


@pytest.mark.performance
def test_event_load_report(
    performance_load_app: AppHarness,
    performance_output: Path,
    performance_scale: str,
):
    """Measure production Socket.IO latency and throughput across client counts.

    Args:
        performance_load_app: Running production app.
        performance_output: Artifact directory.
        performance_scale: Selected scenario scale.
    """
    scales = {
        "smoke": ([1, 5], 3),
        "release": ([1, 10, 50, 200], 50),
    }
    client_counts, events_per_client = scales[performance_scale]
    backend_url = get_config().api_url.rstrip("/")
    handler_name = next(
        name
        for name in RegistrationContext.get().event_handlers
        if name.endswith(".increment") and "performance_load" in name
    )
    payload = {
        "name": handler_name,
        "payload": {},
        "router_data": {"path": "/", "pathname": "/", "query": {}},
    }
    report = PerformanceReport(
        "event-load",
        metadata={"scale": performance_scale, "backend_url": backend_url},
    )

    for clients in client_counts:
        started = time.perf_counter_ns()
        results = asyncio.run(
            run_clients(
                clients,
                lambda index, executor, clients=clients: run_socket_client(
                    backend_url,
                    f"load-token-{clients}-{index}",
                    payload,
                    events_per_client,
                    executor=executor,
                ),
            )
        )
        elapsed_seconds = (time.perf_counter_ns() - started) / 1_000_000_000
        latencies = [latency for result in results for latency in result.latencies_ms]
        errors = [error for result in results for error in result.errors]
        per_client_max = [max(result.latencies_ms, default=0) for result in results]
        expected = clients * events_per_client
        report.add(
            BenchmarkResult(
                name=f"unique_tokens_{clients}_clients",
                parameters={
                    "clients": clients,
                    "events_per_client": events_per_client,
                },
                observations_ms=latencies,
                metrics={
                    "throughput_events_per_second": len(latencies) / elapsed_seconds,
                    "errors": len(errors),
                    "expected_updates": expected,
                    "received_updates": len(latencies),
                    "fairness_spread_ms": max(per_client_max, default=0)
                    - min(per_client_max, default=0),
                },
                measurement_iterations=len(latencies),
            )
        )
        assert not errors, errors
        assert len(latencies) == expected

    report.write(performance_output / "event-load.json")
