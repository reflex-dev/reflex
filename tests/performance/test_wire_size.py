"""Wire-size benchmarks: serialized delta bytes per canonical interaction."""

from __future__ import annotations

import gzip
from collections.abc import Callable
from pathlib import Path

import pytest
from reflex_base.utils.format import json_dumps

from reflex.state import StateUpdate
from tests.benchmarks.support import BenchmarkResult, PerformanceReport
from tests.benchmarks.support.states import PerformanceState, initialized_state

STATE_SIZE = 1000


def _scalar_change(state: PerformanceState) -> None:
    """Increment the scalar counter."""
    state.counter += 1


def _list_append(state: PerformanceState) -> None:
    """Append one element to the list value."""
    state.numbers.append(STATE_SIZE)


def _partial_row_update(state: PerformanceState) -> None:
    """Mutate a single element in the middle of the list value."""
    state.numbers[STATE_SIZE // 2] += 1


def _mapping_update(state: PerformanceState) -> None:
    """Update one existing mapping entry."""
    state.mapping["key_0"] += 1


def _large_append(state: PerformanceState) -> None:
    """Extend the list value by a thousand elements."""
    state.numbers.extend(range(STATE_SIZE))


INTERACTIONS: dict[str, Callable[[PerformanceState], None]] = {
    "scalar_change": _scalar_change,
    "list_append": _list_append,
    "partial_row_update": _partial_row_update,
    "mapping_update": _mapping_update,
    "large_append": _large_append,
}


@pytest.mark.performance
def test_wire_size_report(performance_output: Path, performance_scale: str):
    """Record serialized state-update bytes for canonical interactions.

    Wire bytes regress silently: they are invisible to timing benchmarks on a
    local network but dominate update latency on real links. Each interaction
    mutates a warm state and serializes the resulting update exactly as the
    event pipeline would.

    Args:
        performance_output: Artifact directory.
        performance_scale: Selected scenario scale.
    """
    report = PerformanceReport("wire-size", metadata={"scale": performance_scale})
    sizes: dict[str, int] = {}
    for name, interaction in INTERACTIONS.items():
        state = initialized_state(STATE_SIZE)
        interaction(state)
        # Match the compact separators python-socketio uses when it encodes the
        # event packet (Packet.encode calls dumps(..., separators=(",", ":"))),
        # so wire_bytes equals the real payload size rather than json's spaced
        # default, which overstates it by roughly a fifth.
        wire = json_dumps(
            StateUpdate(delta=state.get_delta()), separators=(",", ":")
        ).encode()
        sizes[name] = len(wire)
        report.add(
            BenchmarkResult(
                name=name,
                parameters={"state_size": STATE_SIZE},
                observations_ms=[],
                metrics={
                    "wire_bytes": len(wire),
                    "wire_gzip_bytes": len(gzip.compress(wire)),
                },
            )
        )

    report.write(performance_output / "wire-size.json")
    assert all(size > 0 for size in sizes.values())
    # A scalar change must stay far below a whole-collection resend.
    assert sizes["scalar_change"] < sizes["large_append"]
