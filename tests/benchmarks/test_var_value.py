"""Benchmarks for resolving and setting vars with get_var_value and set_var_value.

A handler that is handed a var, rather than naming an attribute itself, goes
through these: a form field bound to ``State.people[0].address.city`` reads and
writes the value its var points at on every change. Each routine resolves a var
of one shape a fixed number of times in a single coroutine: a plain field, an
attribute read through an array item, a read whose index is a var, and writes
matching the first two, the nested one going through the field's MutableProxy.

The vars are built outside the measured body, as a handler receives them ready.
"""

import asyncio
import dataclasses
from collections.abc import Callable, Coroutine
from typing import Any

import pytest
from pytest_codspeed import BenchmarkFixture

import reflex as rx
from reflex.state import BaseState

# How many times each routine resolves its var. A nested read costs a few
# microseconds uninstrumented, so even the plain field read keeps every measured
# call above the ~100 microseconds the benchmark README asks for.
N = 1_000


@dataclasses.dataclass
class Address:
    """The innermost object the nested vars read into."""

    city: str = "Berlin"


@dataclasses.dataclass
class Person:
    """An array item holding an object and a list."""

    address: Address = dataclasses.field(default_factory=Address)
    tags: list[str] = dataclasses.field(default_factory=lambda: ["a", "b"])


class VarValueState(BaseState):
    """The state whose vars the routines resolve."""

    count: rx.Field[int] = rx.field(0)
    index: rx.Field[int] = rx.field(0)
    people: rx.Field[list[Person]] = rx.field([Person()])


FIELD = VarValueState.count
NESTED = VarValueState.people[0].address.city
VAR_KEY = VarValueState.people[VarValueState.index].tags.to(list[str])[1]


async def _get_field(state: VarValueState) -> None:
    for _ in range(N):
        await state.get_var_value(FIELD)


async def _get_nested(state: VarValueState) -> None:
    for _ in range(N):
        await state.get_var_value(NESTED)


async def _get_var_key(state: VarValueState) -> None:
    for _ in range(N):
        await state.get_var_value(VAR_KEY)


async def _set_field(state: VarValueState) -> None:
    for i in range(N):
        await state.set_var_value(FIELD, i)


async def _set_nested(state: VarValueState) -> None:
    for _ in range(N):
        await state.set_var_value(NESTED, "Hamburg")


@pytest.fixture(
    params=[
        pytest.param(_get_field, id="get_field"),
        pytest.param(_get_nested, id="get_nested"),
        pytest.param(_get_var_key, id="get_var_key"),
        pytest.param(_set_field, id="set_field"),
        pytest.param(_set_nested, id="set_nested"),
    ]
)
def routine(
    request: pytest.FixtureRequest,
) -> Callable[[VarValueState], Coroutine[Any, Any, None]]:
    """A parametrized get_var_value or set_var_value routine.

    Args:
        request: The pytest fixture request carrying the routine.

    Returns:
        The routine to benchmark.
    """
    return request.param


def test_var_value(
    routine: Callable[[VarValueState], Coroutine[Any, Any, None]],
    benchmark: BenchmarkFixture,
):
    """Benchmark resolving or setting one shape of var on a state.

    Args:
        routine: The parametrized routine.
        benchmark: The codspeed benchmark fixture.
    """
    state = VarValueState(_reflex_internal_init=True)  # pyright: ignore [reportCallIssue]
    loop = asyncio.new_event_loop()
    try:
        benchmark(lambda: loop.run_until_complete(routine(state)))
    finally:
        loop.close()
