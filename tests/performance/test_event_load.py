"""Production Socket.IO concurrency, throughput, and tail-latency benchmarks."""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import Any

import pytest
from reflex_base.config import get_config
from reflex_base.registry import RegistrationContext

from reflex.testing import AppHarness
from tests.benchmarks.support import BenchmarkResult, PerformanceReport, percentile
from tests.benchmarks.support.baseline_server import BaselineSocketServer
from tests.benchmarks.support.report import current_process_metrics
from tests.benchmarks.support.socket_client import (
    run_clients,
    run_reconnect_client,
    run_socket_client,
)

# A load level saturates once p99 exceeds the single-client baseline by this
# factor and by this absolute margin, so tiny baselines do not flag noise.
KNEE_P99_FACTOR = 3.0
KNEE_P99_MARGIN_MS = 25.0


def _increment_payload() -> dict[str, Any]:
    """Build the increment event payload for the running load app.

    Returns:
        Socket.IO event payload targeting the app's increment handler.
    """
    handler_name = next(
        name
        for name in RegistrationContext.get().event_handlers
        if name.endswith(".increment") and "performance_load" in name
    )
    return {
        "name": handler_name,
        "payload": {},
        "router_data": {"path": "/", "pathname": "/", "query": {}},
    }


def _backend_url() -> str:
    """Return the running backend's Socket.IO URL.

    Returns:
        Backend URL without a trailing slash.
    """
    return get_config().api_url.rstrip("/")


@pytest.mark.performance
def test_event_load_report(
    performance_load_app: AppHarness,
    performance_output: Path,
    performance_scale: str,
):
    """Measure production Socket.IO latency and throughput across client counts.

    Reports the full latency-throughput curve and the saturation knee: the
    first load level whose p99 exceeds the single-client baseline by both
    ``KNEE_P99_FACTOR`` and ``KNEE_P99_MARGIN_MS``.

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
    backend_url = _backend_url()
    payload = _increment_payload()
    report = PerformanceReport(
        "event-load",
        metadata={"scale": performance_scale, "backend_url": backend_url},
    )

    curve: list[dict[str, float | int]] = []
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
        payload_sizes = [size for result in results for size in result.payload_bytes]
        errors = [error for result in results for error in result.errors]
        per_client_max = [max(result.latencies_ms, default=0) for result in results]
        expected = clients * events_per_client
        throughput = len(latencies) / elapsed_seconds
        p99 = percentile(latencies, 99)
        curve.append({
            "clients": clients,
            "throughput_events_per_second": throughput,
            "p50_ms": percentile(latencies, 50),
            "p99_ms": p99,
        })
        report.add(
            BenchmarkResult(
                name=f"unique_tokens_{clients}_clients",
                parameters={
                    "clients": clients,
                    "events_per_client": events_per_client,
                },
                observations_ms=latencies,
                metrics={
                    "throughput_events_per_second": throughput,
                    "errors": len(errors),
                    "expected_updates": expected,
                    "received_updates": len(latencies),
                    "fairness_spread_ms": max(per_client_max, default=0)
                    - min(per_client_max, default=0),
                    "payload_bytes_mean": sum(payload_sizes) / len(payload_sizes)
                    if payload_sizes
                    else 0,
                    "payload_bytes_max": max(payload_sizes, default=0),
                },
                measurement_iterations=len(latencies),
            )
        )
        assert not errors, errors
        assert len(latencies) == expected

    baseline_p99 = curve[0]["p99_ms"]
    knee_threshold = max(
        baseline_p99 * KNEE_P99_FACTOR, baseline_p99 + KNEE_P99_MARGIN_MS
    )
    knee_clients = next(
        (level["clients"] for level in curve[1:] if level["p99_ms"] > knee_threshold),
        0,
    )
    report.metadata["latency_curve"] = curve
    report.metadata["knee_threshold_ms"] = knee_threshold
    report.metadata["knee_clients"] = knee_clients

    report.write(performance_output / "event-load.json")


@pytest.mark.performance
def test_framework_overhead_report(
    performance_load_app: AppHarness,
    performance_output: Path,
    performance_scale: str,
):
    """Compare Reflex round-trips against the bare Starlette+Socket.IO substrate.

    Runs the same client, event payload, and response size against a bare
    ``uvicorn`` + Starlette + python-socketio echo server, isolating how much
    of the round-trip is Reflex's event pipeline versus the substrate.

    Args:
        performance_load_app: Running production app.
        performance_output: Artifact directory.
        performance_scale: Selected scenario scale.
    """
    events, warmup = {"smoke": (25, 5), "release": (500, 20)}[performance_scale]
    payload = _increment_payload()

    reflex_result = asyncio.run(
        run_socket_client(_backend_url(), "overhead-reflex", payload, events + warmup)
    )
    assert not reflex_result.errors, reflex_result.errors

    # Pad the canned response so both servers answer with equal payload bytes.
    response_bytes = max(reflex_result.payload_bytes, default=0)
    canned: dict[str, Any] = {"delta": {"state": {"count": 1}}, "final": True}
    base_bytes = len(json.dumps(canned | {"pad": ""}, separators=(",", ":")))
    canned["pad"] = "x" * max(0, response_bytes - base_bytes)
    with BaselineSocketServer(canned) as baseline:
        baseline_result = asyncio.run(
            run_socket_client(
                baseline.url, "overhead-baseline", payload, events + warmup
            )
        )
    assert not baseline_result.errors, baseline_result.errors

    report = PerformanceReport(
        "framework-overhead",
        metadata={"scale": performance_scale, "response_bytes": response_bytes},
    )
    reflex_latencies = reflex_result.latencies_ms[warmup:]
    baseline_latencies = baseline_result.latencies_ms[warmup:]
    for name, latencies in [
        ("reflex_round_trip", reflex_latencies),
        ("bare_starlette_round_trip", baseline_latencies),
    ]:
        report.add(
            BenchmarkResult(
                name=name,
                parameters={"events": events},
                observations_ms=list(latencies),
                metrics={},
                warmup_iterations=warmup,
                measurement_iterations=len(latencies),
            )
        )
    reflex_p50 = percentile(reflex_latencies, 50)
    baseline_p50 = percentile(baseline_latencies, 50)
    report.add(
        BenchmarkResult(
            name="framework_overhead",
            parameters={"events": events},
            observations_ms=[],
            metrics={
                "overhead_p50_ms": reflex_p50 - baseline_p50,
                "overhead_p99_ms": percentile(reflex_latencies, 99)
                - percentile(baseline_latencies, 99),
                "overhead_ratio_p50": reflex_p50 / baseline_p50 if baseline_p50 else 0,
            },
        )
    )
    report.write(performance_output / "framework-overhead.json")
    assert reflex_p50 > 0
    assert baseline_p50 > 0


@pytest.mark.performance
def test_reconnect_storm_report(
    performance_load_app: AppHarness,
    performance_output: Path,
    performance_scale: str,
):
    """Measure simultaneous reconnection after all clients drop.

    Primes per-token state, then reconnects every client at once — the
    deploy-restart storm — measuring connect and first-update latency
    percentiles and resident-memory growth.

    Args:
        performance_load_app: Running production app.
        performance_output: Artifact directory.
        performance_scale: Selected scenario scale.
    """
    clients = {"smoke": 5, "release": 100}[performance_scale]
    backend_url = _backend_url()
    payload = _increment_payload()
    tokens = [f"storm-token-{index}" for index in range(clients)]

    # Prime each token so the storm exercises state restore, not creation.
    prime_results = asyncio.run(
        run_clients(
            clients,
            lambda index, executor: run_socket_client(
                backend_url, tokens[index], payload, 1, executor=executor
            ),
        )
    )
    assert not any(result.errors for result in prime_results)
    # Token disconnect cleanup is fire-and-forget; let it finish so the storm
    # exercises reconnection instead of duplicate-tab handling.
    time.sleep(1)

    rss_before = current_process_metrics()["rss_bytes"]
    started = time.perf_counter_ns()
    storm_results = asyncio.run(
        run_clients(
            clients,
            lambda index, executor: run_reconnect_client(
                backend_url, tokens[index], payload, executor=executor
            ),
        )
    )
    storm_seconds = (time.perf_counter_ns() - started) / 1_000_000_000
    rss_after = current_process_metrics()["rss_bytes"]

    errors = [error for result in storm_results for error in result.errors]
    connects = [result.connect_ms for result in storm_results]
    first_responses = [result.first_response_ms for result in storm_results]
    report = PerformanceReport(
        "reconnect-storm",
        metadata={"scale": performance_scale, "backend_url": backend_url},
    )
    report.add(
        BenchmarkResult(
            name=f"reconnect_storm_{clients}_clients",
            parameters={"clients": clients},
            observations_ms=first_responses,
            metrics={
                "connect_p50_ms": percentile(connects, 50),
                "connect_p99_ms": percentile(connects, 99),
                "connect_max_ms": max(connects, default=0),
                "storm_seconds": storm_seconds,
                "reconnects_per_second": clients / storm_seconds,
                "rss_growth_bytes": rss_after - rss_before,
                "errors": len(errors),
            },
            measurement_iterations=clients,
        )
    )
    report.write(performance_output / "reconnect-storm.json")
    assert not errors, errors
