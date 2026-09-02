"""Benchmarks for state dirty tracking.

Each ``__setattr__`` on a base var records the name in ``dirty_vars`` and
cascades through ``_var_dependencies`` to invalidate dependent computed vars.
These benchmarks isolate the cost of that cascade for the common shapes:
many writes in one handler, a var fanning out to many computed vars, a chain
of computed vars, writes that do not change the value, and the final
``get_delta`` that recomputes and serializes.
"""

import pytest
from pytest_codspeed import BenchmarkFixture

import reflex as rx

N_WRITES = 200
N_FANOUT = 50
N_CHAIN = 20


def _make_fan(i: int):
    def fget(self) -> int:
        return self.source + i

    fget.__name__ = f"dep_{i}"
    return rx.var(fget)


def _make_link(i: int):
    prev = "head" if i == 0 else f"link_{i - 1}"

    def fget(self) -> int:
        return getattr(self, prev) + 1

    fget.__name__ = f"link_{i}"
    return rx.var(fget, deps=[prev])


# One base var feeding N_FANOUT computed vars, plus a var nothing depends on.
FanOutState = type(
    "FanOutState",
    (rx.State,),
    {
        "__module__": __name__,
        "__annotations__": {"source": int, "unrelated": int},
        "source": 0,
        "unrelated": 0,
        **{f"dep_{i}": _make_fan(i) for i in range(N_FANOUT)},
    },
)

# A base var feeding a chain of N_CHAIN computed vars, each depending on the previous.
ChainState = type(
    "ChainState",
    (rx.State,),
    {
        "__module__": __name__,
        "__annotations__": {"head": int},
        "head": 0,
        **{f"link_{i}": _make_link(i) for i in range(N_CHAIN)},
    },
)


def _fresh(state_cls: type[rx.State]) -> rx.State:
    state = state_cls()  # pyright: ignore [reportCallIssue]
    state.dict()  # prime computed var caches
    state._clean()
    return state


def test_many_writes_no_dependents(benchmark: BenchmarkFixture):
    """N assignments to a var with no dependent computed vars."""
    state = _fresh(FanOutState)

    def run():
        for i in range(N_WRITES):
            state.unrelated = i
        state._clean()

    benchmark(run)


def test_many_writes_with_fanout(benchmark: BenchmarkFixture):
    """N assignments to a var that N_FANOUT computed vars depend on."""
    state = _fresh(FanOutState)

    def run():
        for i in range(N_WRITES):
            state.source = i
        state._clean()

    benchmark(run)


def test_many_unchanged_writes(benchmark: BenchmarkFixture):
    """N assignments of the value already stored."""
    state = _fresh(FanOutState)
    state.source = 7
    state._clean()

    def run():
        for _ in range(N_WRITES):
            state.source = 7
        state._clean()

    benchmark(run)


def test_chain_write_and_delta(benchmark: BenchmarkFixture):
    """One write at the head of a computed var chain, then get_delta."""
    state = _fresh(ChainState)
    value = [0]

    def run():
        value[0] += 1
        state.head = value[0]
        state.get_delta()
        state._clean()

    benchmark(run)


def test_fanout_write_and_delta(benchmark: BenchmarkFixture):
    """One write that fans out to N_FANOUT computed vars, then get_delta."""
    state = _fresh(FanOutState)
    value = [0]

    def run():
        value[0] += 1
        state.source = value[0]
        state.get_delta()
        state._clean()

    benchmark(run)


@pytest.mark.parametrize("state_cls", [FanOutState, ChainState])
def test_get_delta_clean(state_cls, benchmark: BenchmarkFixture):
    """get_delta on a state with nothing dirty (the per-event floor)."""
    state = _fresh(state_cls)
    benchmark(state.get_delta)
