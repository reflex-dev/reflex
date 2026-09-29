"""Benchmarks for deadline lookup and refresh with many in-memory sessions."""

import asyncio
import itertools
from types import SimpleNamespace

import pytest
from pytest_codspeed import BenchmarkFixture

from reflex.istate.manager import memory
from reflex.istate.manager.memory import StateManagerMemory
from reflex.istate.manager.token import StateToken


@pytest.fixture(params=[1000, 10000])
def expiration_manager(
    request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch
) -> tuple[StateManagerMemory, list[StateToken]]:
    """Populate deadline bookkeeping without scheduling a background worker.

    Args:
        request: The parametrized retained-session count.
        monkeypatch: The pytest monkeypatch fixture.

    Returns:
        The manager and its retained session tokens.
    """
    manager = StateManagerMemory(token_expiration=3600)
    monkeypatch.setattr(manager, "_ensure_expiration_task", lambda: None)
    tokens = [StateToken(ident=str(i), cls=dict) for i in range(request.param)]
    for token in tokens:
        manager._track_token(token)
    return manager, tokens


def test_next_memory_expiration(
    expiration_manager: tuple[StateManagerMemory, list[StateToken]],
    benchmark: BenchmarkFixture,
):
    """Find the next deadline while no retained sessions have expired.

    Args:
        expiration_manager: The manager and its retained session tokens.
        benchmark: The CodSpeed benchmark fixture.
    """
    manager, _ = expiration_manager
    benchmark(manager._purge_expired_tokens)


def test_refresh_memory_expiration(
    expiration_manager: tuple[StateManagerMemory, list[StateToken]],
    benchmark: BenchmarkFixture,
):
    """Refresh session deadlines in rotation to include index maintenance costs.

    Args:
        expiration_manager: The manager and its retained session tokens.
        benchmark: The CodSpeed benchmark fixture.
    """
    manager, tokens = expiration_manager
    cycle = itertools.cycle(tokens)
    benchmark(lambda: manager._track_token(next(cycle)))


@pytest.mark.parametrize("count", [1000, 10000])
@pytest.mark.parametrize(
    "shape", ["all_due", "half_due", "all_held", "held_and_future"]
)
def test_memory_expiration_batches(
    count: int,
    shape: str,
    monkeypatch: pytest.MonkeyPatch,
    benchmark: BenchmarkFixture,
):
    """Expire coalesced deadlines with setup excluded from measured work.

    Args:
        count: The number of retained sessions.
        shape: The distribution of due and held deadlines.
        monkeypatch: The pytest monkeypatch fixture.
        benchmark: The CodSpeed benchmark fixture.
    """
    clock = SimpleNamespace(now=1000.0)
    monkeypatch.setattr(memory, "time", SimpleNamespace(time=lambda: clock.now))

    def setup():
        """Create a fresh manager before each timed expiration pass.

        Returns:
            The manager argument and empty keyword arguments for the benchmark.
        """
        manager = StateManagerMemory(token_expiration=10)
        monkeypatch.setattr(manager, "_ensure_expiration_task", lambda: None)
        for index in range(count):
            future = shape in {"half_due", "held_and_future"} and index >= count // 2
            held = shape == "all_held" or (
                shape == "held_and_future" and index < count // 2
            )
            clock.now = 1020.0 if future else 1000.0
            token = StateToken(ident=str(index), cls=dict)
            manager.states[token.cache_key] = None
            manager._track_token(token)
            lock = asyncio.Lock()
            if held:
                # Only locked() is read during expiration; no task owns these fixtures.
                monkeypatch.setattr(lock, "_locked", True)
            manager._states_locks[token.lock_key] = lock
        clock.now = 1011.0
        return (manager,), {}

    benchmark.pedantic(
        StateManagerMemory._purge_expired_tokens,
        setup=setup,
        rounds=5,
    )
