"""Benchmarks for dirty propagation and state delta generation."""

from typing import Any

import pytest
from pytest_codspeed import BenchmarkFixture

from .support.states import (
    PerformanceState,
    computed_fanout_state,
    initialized_state,
    state_tree,
)

# One mutation and delta of a small state takes a few microseconds, so the
# benchmarks built on _mutate_counter repeat it this many times per measured call.
MUTATIONS = 50
# Items validated per measured call by test_state_collection_assignment.
ASSIGNED_ITEMS = 100_000


def _mutate_counter(state: Any) -> dict:
    """Increment the counter, calculate the delta and clean the state, repeatedly.

    Args:
        state: The state to mutate, declaring an int ``counter`` field.

    Returns:
        The last delta.
    """
    delta = {}
    for _ in range(MUTATIONS):
        state.counter += 1
        delta = state.get_delta()
        state._clean()
    return delta


@pytest.mark.parametrize("size", [10, 100, 1000, 10_000])
def test_state_delta_scalar_mutation(size: int, benchmark: BenchmarkFixture):
    """Benchmark a scalar mutation and delta extraction across state sizes.

    Args:
        size: Mutable collection size carried by the state.
        benchmark: The CodSpeed benchmark fixture.
    """
    assert benchmark(_mutate_counter, initialized_state(size))


@pytest.mark.parametrize("appends", [1, 10, 100])
def test_dirty_computed_var_propagation(
    appends: int,
    benchmark: BenchmarkFixture,
):
    """Benchmark repeated mutable updates with computed dependencies.

    Args:
        appends: Number of mutations in one measured operation.
        benchmark: The CodSpeed benchmark fixture.
    """

    def setup():
        """Create a stable state for one measured round.

        Returns:
            CodSpeed pedantic positional and keyword arguments.
        """
        state = initialized_state(10)
        _ = state.doubled_total
        state._clean()
        return ((state,), {})

    def append_and_recompute(state: PerformanceState) -> int:
        """Append values and resolve the dependent computed var.

        Args:
            state: Fresh state for this measured round.

        Returns:
            Recomputed aggregate.
        """
        for value in range(appends):
            state.numbers.append(value)
        result = state.doubled_total
        state._clean()
        return result

    assert benchmark.pedantic(append_and_recompute, setup=setup) >= 0


@pytest.mark.parametrize("fanout", [0, 2, 10, 50])
def test_computed_dependency_fanout(fanout: int, benchmark: BenchmarkFixture):
    """Benchmark dirty propagation across a controlled dependency fan-out.

    Args:
        fanout: Number of cached vars directly depending on one source field.
        benchmark: The CodSpeed benchmark fixture.
    """
    with computed_fanout_state(fanout) as (state, names):
        for name in names:
            getattr(state, name)
        state._clean()
        assert benchmark(_mutate_counter, state)


def test_resolved_delta(benchmark: BenchmarkFixture):
    """Benchmark the async resolved-delta path used by event processing.

    Args:
        benchmark: The CodSpeed benchmark fixture.
    """
    import asyncio

    state = initialized_state(1000)
    loop = asyncio.new_event_loop()

    def resolve_delta():
        """Mutate and resolve the full delta.

        Returns:
            Resolved state delta.
        """
        state.counter += 1
        delta = loop.run_until_complete(state._get_resolved_delta())
        state._clean()
        return delta

    try:
        assert benchmark(resolve_delta)
    finally:
        loop.close()


@pytest.mark.parametrize("shape", ["depth_10", "width_10", "three_by_three"])
def test_state_tree_delta(shape: str, benchmark: BenchmarkFixture):
    """Benchmark delta traversal through representative substate shapes.

    Args:
        shape: Registered hierarchy shape.
        benchmark: The CodSpeed benchmark fixture.
    """
    contexts = []

    def setup():
        """Create an isolated hierarchy for one measured round.

        Returns:
            CodSpeed pedantic positional and keyword arguments.
        """
        context = state_tree(shape)
        root = context.__enter__()
        contexts.append(context)
        return ((root,), {})

    def mutate_and_delta(root):
        """Mutate every performance substate and calculate one root delta.

        Args:
            root: Root state.

        Returns:
            Root delta.
        """
        stack = [root]
        while stack:
            state = stack.pop()
            stack.extend(state.substates.values())
            if hasattr(state, "counter"):
                state.counter += 1
        return root.get_delta()

    def teardown(_root) -> None:
        """Detach the isolated registration context."""
        contexts.pop().__exit__(None, None, None)

    assert benchmark.pedantic(
        mutate_and_delta,
        setup=setup,
        teardown=teardown,
    )


@pytest.mark.parametrize("size", [10, 1000, 100_000])
def test_state_collection_assignment(size: int, benchmark: BenchmarkFixture):
    """Benchmark state assignment and its type-validation hot path.

    Every size validates ``ASSIGNED_ITEMS`` items per measured call, in
    ``ASSIGNED_ITEMS // size`` assignments, so the sizes differ only in how the
    work splits between the cost of an assignment and the cost of an item.

    Args:
        size: Assigned list size.
        benchmark: The CodSpeed benchmark fixture.
    """
    values = list(range(size))
    assignments = ASSIGNED_ITEMS // size

    def setup():
        """Create a fresh state for one measured call.

        Returns:
            CodSpeed pedantic positional and keyword arguments.
        """
        return ((initialized_state(0),), {})

    def assign(state: PerformanceState) -> int:
        """Assign the representative collection repeatedly.

        Args:
            state: Fresh state.

        Returns:
            Assigned collection size.
        """
        for _ in range(assignments):
            state.numbers = values
        return len(state.numbers)

    assert benchmark.pedantic(assign, setup=setup) == size
