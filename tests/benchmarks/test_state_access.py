"""Benchmarks for reading and writing state vars and looking up event handlers.

Each routine accesses a scalar var (so no ``MutableProxy`` is involved) of the
state it is declared on, or of a parent state through a substate, where the
access resolves to the parent instance that stores the value.
"""

from collections.abc import Callable

import pytest
from pytest_codspeed import BenchmarkFixture

import reflex as rx

N = 10_000


class AccessParentState(rx.State):
    """The parent state declaring the inherited var."""

    inherited: int = 0

    @rx.var
    def doubled(self) -> int:
        """A cached computed var depending on the inherited var.

        Returns:
            Twice the inherited var.
        """
        return self.inherited * 2

    def handler(self):
        """An event handler looked up through the substate."""


class AccessChildState(AccessParentState):
    """The substate the benchmarks access vars through."""

    own: int = 0


def _read_own(state: AccessChildState) -> None:
    for _ in range(N):
        _ = state.own


def _read_inherited(state: AccessChildState) -> None:
    for _ in range(N):
        _ = state.inherited


def _write_own(state: AccessChildState) -> None:
    for i in range(N):
        state.own = i


def _write_inherited(state: AccessChildState) -> None:
    for i in range(N):
        state.inherited = i


def _read_cached_computed(state: AccessChildState) -> None:
    for _ in range(N):
        _ = state.doubled


def _get_handler(state: AccessChildState) -> None:
    for _ in range(N):
        _ = state.handler


@pytest.fixture(
    params=[
        pytest.param(_read_own, id="read_own"),
        pytest.param(_read_inherited, id="read_inherited"),
        pytest.param(_write_own, id="write_own"),
        pytest.param(_write_inherited, id="write_inherited"),
        pytest.param(_read_cached_computed, id="read_cached_computed"),
        pytest.param(_get_handler, id="get_handler"),
    ]
)
def access_fn(request: pytest.FixtureRequest) -> Callable[[AccessChildState], None]:
    """A parametrized state access routine.

    Args:
        request: The pytest fixture request carrying the access routine.

    Returns:
        The access routine to benchmark.
    """
    return request.param


def test_state_access(access_fn, benchmark: BenchmarkFixture):
    """Benchmark accessing vars and handlers through a substate instance.

    Args:
        access_fn: The parametrized access routine.
        benchmark: The codspeed benchmark fixture.
    """
    parent = AccessParentState()  # pyright: ignore [reportCallIssue]
    state = parent.substates[AccessChildState.get_name()]
    benchmark(lambda: access_fn(state))  # pyright: ignore [reportArgumentType]
