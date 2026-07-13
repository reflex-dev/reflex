"""Real-Redis state-manager latency and command benchmarks."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

import pytest

from reflex.istate.manager.token import StateToken
from tests.benchmarks.support import BenchmarkResult, EventLoopProbe, PerformanceReport
from tests.benchmarks.support.redis import real_redis_state_manager
from tests.benchmarks.support.states import PerformanceState


async def _measure(
    operation: Callable[[], Awaitable[Any]],
    iterations: int,
) -> list[float]:
    """Measure sequential async operations.

    Args:
        operation: Async operation factory.
        iterations: Number of calls.

    Returns:
        Per-call latencies in milliseconds.
    """
    observations = []
    for _ in range(iterations):
        started = time.perf_counter_ns()
        await operation()
        observations.append((time.perf_counter_ns() - started) / 1_000_000)
    return observations


def _command_calls(info: dict[str, Any]) -> int:
    """Sum Redis command calls from ``INFO commandstats``.

    Args:
        info: Redis commandstats mapping.

    Returns:
        Total command invocations.
    """
    return sum(
        int(value.get("calls", 0))
        for key, value in info.items()
        if key.startswith("cmdstat_") and isinstance(value, dict)
    )


def _command_counts(info: dict[str, Any]) -> dict[str, int]:
    """Extract per-command call counts.

    Args:
        info: Redis commandstats mapping.

    Returns:
        Command name to call count.
    """
    return {
        key.removeprefix("cmdstat_"): int(value.get("calls", 0))
        for key, value in info.items()
        if key.startswith("cmdstat_") and isinstance(value, dict)
    }


@pytest.mark.performance
async def test_redis_state_manager_report(
    performance_output: Path,
    performance_scale: str,
):
    """Measure cold/warm state access, writes, contention, and large payloads.

    Args:
        performance_output: Artifact directory.
        performance_scale: Selected scenario scale.
    """
    iterations = {"smoke": 5, "release": 200}[performance_scale]
    concurrency = {"smoke": 5, "release": 200}[performance_scale]
    report = PerformanceReport("redis", metadata={"scale": performance_scale})

    async with real_redis_state_manager() as manager:
        before_info = await manager.redis.info("commandstats")
        cold_iteration = 0

        async def cold_get() -> PerformanceState:
            """Fetch a unique uncached state.

            Returns:
                Newly created state.
            """
            nonlocal cold_iteration
            cold_iteration += 1
            token = StateToken(
                ident=f"cold-{cold_iteration}",
                cls=PerformanceState,
            )
            return await manager.get_state(token)

        cold = await _measure(cold_get, iterations)
        warm_token = StateToken(ident="warm", cls=PerformanceState)
        await manager.get_state(warm_token)
        warm = await _measure(lambda: manager.get_state(warm_token), iterations)

        async def modify(token: StateToken[PerformanceState]) -> int:
            """Modify one token under its Redis lock.

            Args:
                token: State token.

            Returns:
                Updated counter.
            """
            async with manager.modify_state(token) as state:
                state.counter += 1
                return state.counter

        async def diagnose_modify() -> dict[str, float | int]:
            """Attribute lock/read, serialization, and flush/write costs.

            Returns:
                Stage timings and serialized byte count.
            """
            context = manager.modify_state(warm_token)
            lock_started = time.perf_counter_ns()
            state = await context.__aenter__()
            lock_read_ms = (time.perf_counter_ns() - lock_started) / 1_000_000
            state.counter += 1
            pickle_started = time.perf_counter_ns()
            serialized = StateToken.serialize(state)
            pickle_ms = (time.perf_counter_ns() - pickle_started) / 1_000_000
            flush_started = time.perf_counter_ns()
            await context.__aexit__(None, None, None)
            flush_write_ms = (time.perf_counter_ns() - flush_started) / 1_000_000
            return {
                "lock_and_read_ms": lock_read_ms,
                "pickle_ms": pickle_ms,
                "serialized_bytes": len(serialized),
                "flush_and_write_ms": flush_write_ms,
            }

        stage_metrics = await diagnose_modify()
        writes = await _measure(lambda: modify(warm_token), iterations)

        async def concurrent(tokens: list[StateToken[PerformanceState]]) -> list[float]:
            """Measure a concurrent batch.

            Args:
                tokens: Token for each concurrent modification.

            Returns:
                Per-operation completion latencies.
            """
            started = time.perf_counter_ns()

            async def timed(token: StateToken[PerformanceState]) -> float:
                """Measure one concurrent modification.

                Args:
                    token: State token.

                Returns:
                    Completion latency from batch start.
                """
                await modify(token)
                return (time.perf_counter_ns() - started) / 1_000_000

            return list(await asyncio.gather(*(timed(token) for token in tokens)))

        probe = EventLoopProbe(interval=0.001)
        async with probe:
            same_token = await concurrent([warm_token] * concurrency)
            independent_tokens = await concurrent([
                StateToken(ident=f"independent-{index}", cls=PerformanceState)
                for index in range(concurrency)
            ])

        large_token = StateToken(ident="large", cls=PerformanceState)

        async def large_write() -> int:
            """Write a state large enough to exercise serialization offloading.

            Returns:
                Number of stored elements.
            """
            async with manager.modify_state(large_token) as state:
                state.numbers = list(range(100_000))
                return len(state.numbers)

        large = await _measure(large_write, 1 if performance_scale == "smoke" else 3)
        after_info = await manager.redis.info("commandstats")

    command_delta = _command_calls(after_info) - _command_calls(before_info)
    before_commands = _command_counts(before_info)
    after_commands = _command_counts(after_info)
    command_metrics = {
        f"redis_command_{command}": count - before_commands.get(command, 0)
        for command, count in after_commands.items()
        if count - before_commands.get(command, 0) > 0
    }
    common_metrics = (
        probe.summary()
        | stage_metrics
        | command_metrics
        | {"redis_commands": command_delta}
    )
    for name, observations, parameters in [
        ("cold_get", cold, {"iterations": iterations}),
        ("warm_get", warm, {"iterations": iterations}),
        ("modify", writes, {"iterations": iterations}),
        ("same_token_contention", same_token, {"concurrency": concurrency}),
        (
            "independent_token_concurrency",
            independent_tokens,
            {"concurrency": concurrency},
        ),
        ("large_state_write", large, {"elements": 100_000}),
    ]:
        report.add(
            BenchmarkResult(
                name,
                parameters,
                observations,
                common_metrics,
                measurement_iterations=len(observations),
            )
        )
    report.write(performance_output / "redis.json")

    assert command_delta > 0
    assert len(same_token) == len(independent_tokens) == concurrency
