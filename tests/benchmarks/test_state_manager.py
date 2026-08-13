"""Deterministic benchmarks for in-memory state-manager operations."""

import asyncio

from pytest_codspeed import BenchmarkFixture

from reflex.istate.manager.memory import StateManagerMemory
from reflex.istate.manager.token import BaseStateToken

from .support.states import (
    PerformanceState,
    get_performance_state,
    isolated_performance_registry,
)


def test_state_manager_memory_cold_get(benchmark: BenchmarkFixture):
    """Benchmark state construction for an uncached token.

    Args:
        benchmark: The CodSpeed benchmark fixture.
    """
    manager = StateManagerMemory()
    loop = asyncio.new_event_loop()
    iteration = 0

    def setup():
        """Return a unique token for one cold measurement."""
        nonlocal iteration
        iteration += 1
        token = BaseStateToken(ident=f"cold-{iteration}", cls=PerformanceState)
        return ((token,), {})

    def get_state(token: BaseStateToken) -> PerformanceState:
        """Fetch a state through the async manager API.

        Returns:
            Managed state.
        """
        return get_performance_state(loop.run_until_complete(manager.get_state(token)))

    def teardown(token: BaseStateToken) -> None:
        """Purge the measured state."""
        manager._purge_token(token)  # pyright: ignore [reportPrivateUsage]

    # Isolate the registry so the measured cold construction instantiates only
    # PerformanceState's subtree, not every state in the collected session.
    with isolated_performance_registry():
        try:
            benchmark.pedantic(get_state, setup=setup, teardown=teardown)
        finally:
            loop.run_until_complete(manager.close())
            loop.close()


def test_state_manager_memory_warm_get(benchmark: BenchmarkFixture):
    """Benchmark state lookup for a cached token.

    Args:
        benchmark: The CodSpeed benchmark fixture.
    """
    manager = StateManagerMemory()
    loop = asyncio.new_event_loop()
    token = BaseStateToken(ident="warm", cls=PerformanceState)
    loop.run_until_complete(manager.get_state(token))

    try:
        state = benchmark(
            lambda: get_performance_state(
                loop.run_until_complete(manager.get_state(token))
            )
        )
        assert isinstance(state, PerformanceState)
    finally:
        loop.run_until_complete(manager.close())
        loop.close()


def test_state_manager_memory_modify(benchmark: BenchmarkFixture):
    """Benchmark lock acquisition, mutation, and release for one token.

    Args:
        benchmark: The CodSpeed benchmark fixture.
    """
    manager = StateManagerMemory()
    loop = asyncio.new_event_loop()
    token = BaseStateToken(ident="modify", cls=PerformanceState)

    async def modify() -> int:
        """Increment one state under the manager lock.

        Returns:
            Updated counter.
        """
        async with manager.modify_state_with_links(token) as root_state:
            state = get_performance_state(root_state)
            state.counter += 1
            return state.counter

    try:
        assert benchmark(lambda: loop.run_until_complete(modify())) > 0
    finally:
        loop.run_until_complete(manager.close())
        loop.close()


def test_state_manager_memory_read_only_modify(benchmark: BenchmarkFixture):
    """Benchmark a read-only lock context that should not produce a write.

    Args:
        benchmark: The CodSpeed benchmark fixture.
    """
    manager = StateManagerMemory()
    loop = asyncio.new_event_loop()
    token = BaseStateToken(ident="read-only", cls=PerformanceState)

    async def read_only() -> int:
        """Read one field under the manager lock.

        Returns:
            Current counter.
        """
        async with manager.modify_state_with_links(token) as root_state:
            state = get_performance_state(root_state)
            return state.counter

    try:
        assert benchmark(lambda: loop.run_until_complete(read_only())) == 0
    finally:
        loop.run_until_complete(manager.close())
        loop.close()
