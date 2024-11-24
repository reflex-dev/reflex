"""Benchmarks for pickling and unpickling states."""

import pickle

import pytest

from reflex.state import State


@pytest.mark.benchmark
def test_pickle(benchmark, big_state: State) -> None:
    """Benchmark pickling a big state.

    Args:
        benchmark: The benchmark fixture.
        big_state: The big state fixture.
    """
    benchmark(pickle.dumps, big_state)


@pytest.mark.benchmark
def test_pickle_highest_protocol(benchmark, big_state: State) -> None:
    """Benchmark pickling a big state.

    Args:
        benchmark: The benchmark fixture.
        big_state: The big state fixture.
    """
    benchmark(pickle.dumps, big_state, protocol=pickle.HIGHEST_PROTOCOL)
