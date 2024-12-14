"""Benchmark for the state manager redis."""

import asyncio
from uuid import uuid4

import pytest
from pytest_benchmark.fixture import BenchmarkFixture

from reflex.state import State, StateManagerRedis
from reflex.utils.prerequisites import get_redis
from reflex.vars.base import computed_var


class RootState(State):
    """Root state class for testing."""

    counter: int = 0
    int_dict: dict[str, int] = {}


class ChildState(RootState):
    """Child state class for testing."""

    child_counter: int = 0

    @computed_var
    def str_dict(self):
        """Convert the int dict to a string dict.

        Returns:
            A dictionary with string keys and integer values.
        """
        return {str(k): v for k, v in self.int_dict.items()}


class ChildState2(RootState):
    """Child state 2 class for testing."""

    child2_counter: int = 0


class GrandChildState(ChildState):
    """Grandchild state class for testing."""

    grand_child_counter: int = 0

    @computed_var
    def double_counter(self):
        """Double the counter.

        Returns:
            The counter value multiplied by 2.
        """
        return self.counter * 2


@pytest.fixture
def state_manager() -> StateManagerRedis:
    """Fixture for the redis state manager.

    Returns:
        An instance of StateManagerRedis.
    """
    redis = get_redis()
    if redis is None:
        pytest.skip("Redis is not available")
    return StateManagerRedis(redis=redis, state=State)


@pytest.fixture
def token() -> str:
    """Fixture for the token.

    Returns:
        A unique token string.
    """
    return str(uuid4())


@pytest.fixture
def grand_child_state_token(token: str) -> str:
    """Fixture for the grand child state token.

    Args:
        token: The token fixture.

    Returns:
        A string combining the token and the grandchild state name.
    """
    return f"{token}_{GrandChildState.get_full_name()}"


@pytest.fixture
def state_token(token: str) -> str:
    """Fixture for the base state token.

    Args:
        token: The token fixture.

    Returns:
        A string combining the token and the base state name.
    """
    return f"{token}_{State.get_full_name()}"


@pytest.fixture
def grand_child_state() -> GrandChildState:
    """Fixture for the grand child state.

    Returns:
        An instance of GrandChildState.
    """
    state = State()

    root = RootState()
    root.parent_state = state
    state.substates[root.get_name()] = root

    child = ChildState()
    child.parent_state = root
    root.substates[child.get_name()] = child

    child2 = ChildState2()
    child2.parent_state = root
    root.substates[child2.get_name()] = child2

    gcs = GrandChildState()
    gcs.parent_state = child
    child.substates[gcs.get_name()] = gcs

    return gcs


@pytest.fixture
def grand_child_state_big(grand_child_state: GrandChildState) -> GrandChildState:
    """Fixture for the grand child state with big data.

    Args:
        grand_child_state: The grand child state fixture.

    Returns:
        An instance of GrandChildState with large data.
    """
    grand_child_state.counter = 100
    grand_child_state.child_counter = 200
    grand_child_state.grand_child_counter = 300
    grand_child_state.int_dict = {str(i): i for i in range(10000)}
    return grand_child_state


def test_set_state(
    benchmark: BenchmarkFixture,
    state_manager: StateManagerRedis,
    event_loop: asyncio.AbstractEventLoop,
    token: str,
) -> None:
    """Benchmark setting state with minimal data.

    Args:
        benchmark: The benchmark fixture.
        state_manager: The state manager fixture.
        event_loop: The event loop fixture.
        token: The token fixture.
    """
    state = State()

    def func():
        event_loop.run_until_complete(state_manager.set_state(token=token, state=state))

    benchmark(func)


def test_get_state(
    benchmark: BenchmarkFixture,
    state_manager: StateManagerRedis,
    event_loop: asyncio.AbstractEventLoop,
    state_token: str,
) -> None:
    """Benchmark getting state with minimal data.

    Args:
        benchmark: The benchmark fixture.
        state_manager: The state manager fixture.
        event_loop: The event loop fixture.
        state_token: The base state token fixture.
    """
    state = State()
    event_loop.run_until_complete(
        state_manager.set_state(token=state_token, state=state)
    )

    def func():
        _ = event_loop.run_until_complete(state_manager.get_state(token=state_token))

    benchmark(func)


def test_set_state_tree_minimal(
    benchmark: BenchmarkFixture,
    state_manager: StateManagerRedis,
    event_loop: asyncio.AbstractEventLoop,
    grand_child_state_token: str,
    grand_child_state: GrandChildState,
) -> None:
    """Benchmark setting state with minimal data.

    Args:
        benchmark: The benchmark fixture.
        state_manager: The state manager fixture.
        event_loop: The event loop fixture.
        grand_child_state_token: The grand child state token fixture.
        grand_child_state: The grand child state fixture.
    """

    def func():
        event_loop.run_until_complete(
            state_manager.set_state(
                token=grand_child_state_token, state=grand_child_state
            )
        )

    benchmark(func)


def test_get_state_tree_minimal(
    benchmark: BenchmarkFixture,
    state_manager: StateManagerRedis,
    event_loop: asyncio.AbstractEventLoop,
    grand_child_state_token: str,
    grand_child_state: GrandChildState,
) -> None:
    """Benchmark getting state with minimal data.

    Args:
        benchmark: The benchmark fixture.
        state_manager: The state manager fixture.
        event_loop: The event loop fixture.
        grand_child_state_token: The grand child state token fixture.
        grand_child_state: The grand child state fixture.
    """
    event_loop.run_until_complete(
        state_manager.set_state(token=grand_child_state_token, state=grand_child_state)
    )

    def func():
        _ = event_loop.run_until_complete(
            state_manager.get_state(token=grand_child_state_token)
        )

    benchmark(func)


def test_set_state_tree_big(
    benchmark: BenchmarkFixture,
    state_manager: StateManagerRedis,
    event_loop: asyncio.AbstractEventLoop,
    grand_child_state_token: str,
    grand_child_state_big: GrandChildState,
) -> None:
    """Benchmark setting state with minimal data.

    Args:
        benchmark: The benchmark fixture.
        state_manager: The state manager fixture.
        event_loop: The event loop fixture.
        grand_child_state_token: The grand child state token fixture.
        grand_child_state_big: The grand child state fixture.
    """

    def func():
        event_loop.run_until_complete(
            state_manager.set_state(
                token=grand_child_state_token, state=grand_child_state_big
            )
        )

    benchmark(func)


def test_get_state_tree_big(
    benchmark: BenchmarkFixture,
    state_manager: StateManagerRedis,
    event_loop: asyncio.AbstractEventLoop,
    grand_child_state_token: str,
    grand_child_state_big: GrandChildState,
) -> None:
    """Benchmark getting state with minimal data.

    Args:
        benchmark: The benchmark fixture.
        state_manager: The state manager fixture.
        event_loop: The event loop fixture.
        grand_child_state_token: The grand child state token fixture.
        grand_child_state_big: The grand child state fixture.
    """
    event_loop.run_until_complete(
        state_manager.set_state(
            token=grand_child_state_token, state=grand_child_state_big
        )
    )

    def func():
        _ = event_loop.run_until_complete(
            state_manager.get_state(token=grand_child_state_token)
        )

    benchmark(func)
