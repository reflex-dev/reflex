"""Backend memory cost per connected session as state size grows."""

from __future__ import annotations

import contextlib
import gc
import json
import subprocess
import sys
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from reflex_base.config import get_config
from reflex_base.registry import RegistrationContext

from reflex.testing import AppHarness
from tests.benchmarks.support import BenchmarkResult, PerformanceReport
from tests.benchmarks.support.report import current_process_metrics

REPO_ROOT = Path(__file__).resolve().parents[2]


def _handler_payload(suffix: str) -> dict[str, Any]:
    """Build an event payload for a load-app handler.

    Args:
        suffix: Handler method name.

    Returns:
        Socket.IO event payload targeting the handler.
    """
    handler_name = next(
        name
        for name in RegistrationContext.get().event_handlers
        if name.endswith(f".{suffix}") and "performance_load" in name
    )
    return {
        "name": handler_name,
        "payload": {},
        "router_data": {"path": "/", "pathname": "/", "query": {}},
    }


@contextlib.contextmanager
def _held_sessions(
    url: str,
    token_prefix: str,
    count: int,
    payload: dict[str, Any],
) -> Iterator[None]:
    """Hold primed sessions from a subprocess so client memory stays external.

    Args:
        url: Backend Socket.IO URL.
        token_prefix: Unique token prefix for this batch.
        count: Number of sessions to hold.
        payload: Priming event payload sent once per session.

    Yields:
        While the sessions are connected and primed.

    Raises:
        RuntimeError: If the holder had to be killed; a holder outliving its
            batch would leak client memory into the next RSS measurement.
    """
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "tests.benchmarks.support.idle_clients",
            url,
            token_prefix,
            str(count),
            json.dumps(payload),
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
        cwd=REPO_ROOT,
    )
    try:
        assert process.stdout is not None
        assert process.stdin is not None
        ready = process.stdout.readline().strip()
        assert ready == "ready", f"session holder failed: {ready!r}"
        yield
    finally:
        if process.stdin is not None:
            with contextlib.suppress(OSError):
                process.stdin.close()
        try:
            process.wait(timeout=30)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
            msg = (
                f"session holder {token_prefix!r} did not exit and was killed; "
                "subsequent RSS measurements would have been invalid"
            )
            raise RuntimeError(msg) from None


def _settled_rss() -> int:
    """Collect garbage, let the loop settle, and read resident memory.

    Returns:
        Resident set size in bytes.
    """
    gc.collect()
    time.sleep(0.2)
    return current_process_metrics()["rss_bytes"]


@pytest.mark.performance
def test_session_memory_report(
    performance_load_app: AppHarness,
    performance_output: Path,
    performance_scale: str,
):
    """Measure marginal backend memory per connected, primed session.

    The capacity-planning number: bytes of backend memory per session at a
    small and a large per-session state, measured between two held batches so
    interpreter warmup does not inflate the marginal cost.

    Args:
        performance_load_app: Running production app.
        performance_output: Artifact directory.
        performance_scale: Selected scenario scale.
    """
    batch = {"smoke": 5, "release": 50}[performance_scale]
    backend_url = get_config().api_url.rstrip("/")
    report = PerformanceReport(
        "session-memory",
        metadata={"scale": performance_scale, "batch": batch},
    )

    for variant, handler in [
        ("small_state", "increment"),
        ("large_state", "append_large"),
    ]:
        payload = _handler_payload(handler)
        rss_start = _settled_rss()
        with _held_sessions(backend_url, f"mem-{variant}-a", batch, payload):
            rss_first = _settled_rss()
            with _held_sessions(backend_url, f"mem-{variant}-b", batch, payload):
                rss_second = _settled_rss()
        report.add(
            BenchmarkResult(
                name=f"session_memory_{variant}",
                parameters={"sessions_per_batch": batch, "handler": handler},
                observations_ms=[],
                metrics={
                    "rss_start_bytes": rss_start,
                    "rss_first_batch_bytes": rss_first,
                    "rss_second_batch_bytes": rss_second,
                    "first_batch_bytes_per_session": (rss_first - rss_start) / batch,
                    "marginal_bytes_per_session": (rss_second - rss_first) / batch,
                },
                measurement_iterations=batch,
            )
        )

    report.write(performance_output / "session-memory.json")
    assert len(report.results) == 2
