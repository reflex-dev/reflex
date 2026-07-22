"""Benchmarks for reading state vars through ``MutableProxy``.

Reading a *mutable* var (list/dict/dataclass) returns a ``MutableProxy`` whose
element reads go through ``_wrap_recursive``, which on every element checks
whether the read originates from ``dataclasses`` internals. Reading a
*non-mutable* var (a scalar) returns the value directly with no proxy. These
benchmarks exercise both paths so the per-element proxy read overhead is
measurable.
"""

import dataclasses

import pytest
from pytest_codspeed import BenchmarkFixture

import reflex as rx

N = 10_000


@dataclasses.dataclass
class Point:
    """A simple dataclass element used to exercise recursive proxy wrapping."""

    x: int
    y: int


class ProxyBenchmarkState(rx.State):
    """State exposing mutable and non-mutable vars for proxy benchmarks."""

    scalar: rx.Field[int] = rx.field(0)
    numbers: rx.Field[list[int]] = rx.field(default_factory=lambda: list(range(N)))
    mapping: rx.Field[dict[int, int]] = rx.field(
        default_factory=lambda: dict.fromkeys(range(N), 0)
    )
    points: rx.Field[list[Point]] = rx.field(
        default_factory=lambda: [Point(i, i) for i in range(N)]
    )


def _read_scalar(state: ProxyBenchmarkState) -> None:
    """Read a non-mutable var repeatedly (returned directly, no proxy)."""
    for _ in range(N):
        _ = state.scalar


def _iter_numbers(state: ProxyBenchmarkState) -> None:
    """Iterate a mutable list var (``__iter__`` wraps each element)."""
    for _ in state.numbers:
        pass


def _index_mapping(state: ProxyBenchmarkState) -> None:
    """Index a mutable dict var (``__getitem__`` wraps each value)."""
    mapping = state.mapping
    for i in range(N):
        _ = mapping[i]


def _iter_points(state: ProxyBenchmarkState) -> None:
    """Iterate a mutable list of dataclasses (recursive proxy wrapping)."""
    for _ in state.points:
        pass


@pytest.fixture(
    params=[
        pytest.param(_read_scalar, id="non_mutable_scalar"),
        pytest.param(_iter_numbers, id="mutable_list"),
        pytest.param(_index_mapping, id="mutable_dict"),
        pytest.param(_iter_points, id="mutable_dataclass_list"),
    ]
)
def access_fn(request: pytest.FixtureRequest):
    """A parametrized var-access routine over mutable and non-mutable vars.

    Args:
        request: The pytest fixture request carrying the access routine.

    Returns:
        The access routine to benchmark.
    """
    return request.param


def test_var_access(access_fn, benchmark: BenchmarkFixture):
    """Benchmark reading a state var for mutable and non-mutable shapes.

    Args:
        access_fn: The parametrized var-access routine.
        benchmark: The codspeed benchmark fixture.
    """
    state = ProxyBenchmarkState()
    benchmark(lambda: access_fn(state))
