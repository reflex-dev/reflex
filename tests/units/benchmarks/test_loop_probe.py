"""Tests for event-loop benchmark probes."""

import asyncio
import time

import pytest

from tests.benchmarks.support.loop_probe import EventLoopProbe


@pytest.mark.asyncio
async def test_event_loop_probe_detects_blocking_work():
    """A synchronous pause is reported as event-loop scheduling lag."""
    interval = 0.001
    async with EventLoopProbe(interval=interval) as probe:
        await asyncio.sleep(interval * 2)
        time.sleep(0.02)  # noqa: ASYNC251 - intentional event-loop blocking
        await asyncio.sleep(interval * 2)

    summary = probe.summary()
    assert summary["sample_count"] >= 2
    assert summary["peak_tasks"] >= 1
    assert summary["lag_max_ms"] >= 10


@pytest.mark.asyncio
async def test_event_loop_probe_detects_terminal_blocking_work():
    """A block immediately before context exit still produces a lag sample."""
    async with EventLoopProbe(interval=0.001) as probe:
        time.sleep(0.02)  # noqa: ASYNC251 - intentional event-loop blocking

    assert probe.summary()["lag_max_ms"] >= 10


@pytest.mark.asyncio
async def test_event_loop_probe_excludes_sampler_task():
    """Task metrics exclude the probe's own sampler task."""
    async with EventLoopProbe(interval=0.001) as probe:
        await asyncio.sleep(0.003)

    assert probe.peak_tasks == 1


@pytest.mark.asyncio
async def test_event_loop_probe_resets_between_runs():
    """Reusing a probe does not mix observations from separate workloads."""
    probe = EventLoopProbe(interval=0.001)
    async with probe:
        await asyncio.sleep(0.005)
    first_sample_count = len(probe.lag_samples)

    async with probe:
        await asyncio.sleep(0.003)

    assert first_sample_count > len(probe.lag_samples)


def test_event_loop_probe_summary_percentiles():
    """Summary values use linearly interpolated lag percentiles."""
    probe = EventLoopProbe()
    probe.lag_samples.extend([0.001, 0.002, 0.003, 0.004, 0.005])

    assert probe.summary() == {
        "sample_count": 5,
        "peak_tasks": 0,
        "lag_p50_ms": 3.0,
        "lag_p95_ms": 4.8,
        "lag_p99_ms": 4.96,
        "lag_max_ms": 5.0,
    }


@pytest.mark.asyncio
async def test_event_loop_probe_rejects_non_positive_interval():
    """Sampling intervals must advance the event-loop clock."""
    with pytest.raises(ValueError, match="greater than zero"):
        async with EventLoopProbe(interval=0):
            pass
