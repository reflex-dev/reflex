"""Allocation and retained-memory performance benchmarks."""

from __future__ import annotations

import gc
import itertools
import time
import tracemalloc
from collections.abc import Callable
from pathlib import Path

import pytest
from reflex_base.utils.format import json_dumps

from reflex.compiler import compiler
from reflex.state import StateUpdate
from reflex.vars import Var
from tests.benchmarks.fixtures import _complicated_page
from tests.benchmarks.support import BenchmarkResult, PerformanceReport
from tests.benchmarks.support.states import initialized_state


def _compile_workload() -> None:
    """Build and compile a representative component tree."""
    assert compiler._compile_page(_complicated_page())


def _state_delta_workload() -> None:
    """Mutate and serialize a state carrying large mutable values."""
    state = initialized_state(1000)
    state.counter += 1
    assert json_dumps(StateUpdate(delta=state.get_delta()))


def _var_workload() -> None:
    """Construct a batch of Var operations and release them."""
    left = Var.create(1)
    right = Var.create(2)
    for _ in range(1000):
        assert ((left + right) * right - left)._js_expr


def _measure_allocations(
    workload: Callable[[], None],
    cycles: int,
) -> tuple[list[float], dict[str, float | int]]:
    """Measure elapsed time, peak allocation, and retained-memory trend.

    Args:
        workload: Workload invoked once per cycle.
        cycles: Measurement cycles after one warmup.

    Returns:
        Cycle latencies and allocation metrics.
    """
    workload()
    gc.collect()
    tracemalloc.start()
    baseline, _ = tracemalloc.get_traced_memory()
    retained: list[int] = []
    latencies: list[float] = []
    peak = baseline
    try:
        for _ in range(cycles):
            started = time.perf_counter_ns()
            workload()
            latencies.append((time.perf_counter_ns() - started) / 1_000_000)
            gc.collect()
            current, current_peak = tracemalloc.get_traced_memory()
            retained.append(current - baseline)
            peak = max(peak, current_peak)
    finally:
        tracemalloc.stop()

    monotonic_growth = all(
        current > previous for previous, current in itertools.pairwise(retained)
    )
    return latencies, {
        "peak_traced_bytes": peak - baseline,
        "retained_bytes": retained[-1] if retained else 0,
        "retained_growth_bytes": retained[-1] - retained[0] if len(retained) > 1 else 0,
        "monotonic_growth": int(monotonic_growth),
    }


@pytest.mark.performance
def test_memory_report(performance_output: Path, performance_scale: str):
    """Profile allocation and retention across compiler and runtime workloads.

    Args:
        performance_output: Artifact directory.
        performance_scale: Selected scenario scale.
    """
    cycles = {"smoke": 3, "release": 100}[performance_scale]
    report = PerformanceReport("memory", metadata={"scale": performance_scale})
    for name, workload in {
        "component_compile": _compile_workload,
        "state_delta_serialization": _state_delta_workload,
        "var_operations": _var_workload,
    }.items():
        observations, metrics = _measure_allocations(workload, cycles)
        report.add(
            BenchmarkResult(
                name=name,
                parameters={"cycles": cycles},
                observations_ms=observations,
                metrics=metrics,
                warmup_iterations=1,
                measurement_iterations=cycles,
            )
        )

    report.write(performance_output / "memory.json")
    assert all(result.metrics["peak_traced_bytes"] >= 0 for result in report.results)
    assert not any(
        result.metrics["monotonic_growth"]
        and result.metrics["retained_growth_bytes"] > 1_000_000
        for result in report.results
    )
