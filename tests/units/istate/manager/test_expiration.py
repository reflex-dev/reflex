"""Tests for state manager token expiration."""

import asyncio
import random
import time
from collections.abc import AsyncGenerator, Callable
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import pytest_asyncio

from reflex.istate.manager import memory
from reflex.istate.manager.memory import StateManagerMemory
from reflex.istate.manager.token import BaseStateToken, StateToken
from reflex.state import BaseState


class ExpiringState(BaseState):
    """A test state for expiration-specific manager tests."""

    value: int = 0


async def _poll_until(
    predicate: Callable[[], bool],
    *,
    timeout: float = 3.0,
    interval: float = 0.05,
):
    """Poll until a predicate succeeds.

    Args:
        predicate: The predicate to evaluate.
        timeout: The maximum time to wait.
        interval: The delay between attempts.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        await asyncio.sleep(interval)
    assert predicate()


@pytest_asyncio.fixture(loop_scope="function")
async def state_manager_memory() -> AsyncGenerator[StateManagerMemory]:
    """Create a memory state manager with a short expiration.

    Yields:
        The memory state manager under test.
    """
    state_manager = StateManagerMemory(token_expiration=1)
    yield state_manager
    await state_manager.close()


@pytest.mark.asyncio
async def test_memory_state_manager_evicts_expired_state(
    state_manager_memory: StateManagerMemory,
    token: str,
):
    """Expired states should be removed from the in-memory cache and locks."""
    state_token = BaseStateToken(ident=token, cls=ExpiringState)

    async with state_manager_memory.modify_state(state_token) as state:
        state.value = 42

    assert token in state_manager_memory.states
    assert token in state_manager_memory._states_locks
    assert token in state_manager_memory._token_expires_at

    await _poll_until(
        lambda: (
            token not in state_manager_memory.states
            and token not in state_manager_memory._states_locks
            and token not in state_manager_memory._token_expires_at
        )
    )


@pytest.mark.asyncio
async def test_memory_state_manager_get_state_refreshes_expiration(
    state_manager_memory: StateManagerMemory,
    token: str,
):
    """Accessing a state should extend its expiration window."""
    state_token = BaseStateToken(ident=token, cls=ExpiringState)
    state = await state_manager_memory.get_state(state_token)
    assert isinstance(state, ExpiringState)
    state.value = 7
    expires_at = state_manager_memory._token_expires_at[token]

    await asyncio.sleep(0.6)

    same_state = await state_manager_memory.get_state(state_token)
    assert same_state is state
    assert state_manager_memory._token_expires_at[token] > expires_at

    await asyncio.sleep(0.6)

    assert token in state_manager_memory.states

    await _poll_until(lambda: token not in state_manager_memory.states)


@pytest.mark.asyncio
async def test_memory_state_manager_set_state_refreshes_expiration(
    state_manager_memory: StateManagerMemory,
    token: str,
):
    """Persisting a state should extend its expiration window."""
    state_token = BaseStateToken(ident=token, cls=ExpiringState)
    state = await state_manager_memory.get_state(state_token)
    assert isinstance(state, ExpiringState)
    state.value = 17
    expires_at = state_manager_memory._token_expires_at[token]

    await asyncio.sleep(0.6)

    await state_manager_memory.set_state(state_token, state)

    assert state_manager_memory._token_expires_at[token] > expires_at

    await asyncio.sleep(0.6)

    assert token in state_manager_memory.states

    await _poll_until(lambda: token not in state_manager_memory.states)


@pytest.mark.asyncio
async def test_memory_state_manager_multiple_accesses_extend_expiration(
    state_manager_memory: StateManagerMemory,
    token: str,
):
    """Repeated accesses should keep the state alive until it goes idle."""
    state_token = BaseStateToken(ident=token, cls=ExpiringState)
    state = await state_manager_memory.get_state(state_token)
    assert isinstance(state, ExpiringState)
    expires_at = state_manager_memory._token_expires_at[token]

    for _ in range(3):
        await asyncio.sleep(0.25)
        assert await state_manager_memory.get_state(state_token) is state
        assert state_manager_memory._token_expires_at[token] > expires_at
        expires_at = state_manager_memory._token_expires_at[token]

    await asyncio.sleep(0.6)

    assert token in state_manager_memory.states

    await _poll_until(lambda: token not in state_manager_memory.states)


@pytest.mark.asyncio
async def test_memory_state_manager_returns_fresh_state_after_eviction(
    state_manager_memory: StateManagerMemory,
    token: str,
):
    """A token should get a fresh state after the previous one expires."""
    state_token = BaseStateToken(ident=token, cls=ExpiringState)
    state = await state_manager_memory.get_state(state_token)
    assert isinstance(state, ExpiringState)
    state.value = 99

    await _poll_until(lambda: token not in state_manager_memory.states)

    fresh_state = await state_manager_memory.get_state(state_token)
    assert isinstance(fresh_state, ExpiringState)
    assert fresh_state is not state
    assert fresh_state.value == 0


@pytest.mark.asyncio
async def test_memory_state_manager_close_cancels_expiration_task(
    state_manager_memory: StateManagerMemory,
    token: str,
):
    """Closing the manager should cancel the expiration task cleanly."""
    await state_manager_memory.get_state(BaseStateToken(ident=token, cls=ExpiringState))

    expiration_task = state_manager_memory._expiration_task
    assert expiration_task is not None
    assert not expiration_task.done()

    await state_manager_memory.close()

    assert state_manager_memory._expiration_task is None
    assert expiration_task.done()

    await state_manager_memory.close()


@pytest.mark.asyncio
async def test_memory_state_manager_refreshes_expiration_after_locked_access(
    state_manager_memory: StateManagerMemory,
    token: str,
):
    """Releasing a long-held state should start a fresh expiration window."""
    state_token = BaseStateToken(ident=token, cls=ExpiringState)

    async with state_manager_memory.modify_state(state_token) as state:
        state.value = 5
        expires_at = state_manager_memory._token_expires_at[token]
        await asyncio.sleep(1.2)
        assert token in state_manager_memory.states

    assert state_manager_memory._token_expires_at[token] > expires_at

    await asyncio.sleep(0.6)

    assert token in state_manager_memory.states

    await _poll_until(lambda: token not in state_manager_memory.states)


@pytest.mark.asyncio
async def test_memory_expiration_does_not_scan_future_tokens(
    monkeypatch: pytest.MonkeyPatch,
):
    """Finding the next deadline should not inspect every retained token.

    Args:
        monkeypatch: The pytest monkeypatch fixture.
    """
    manager = StateManagerMemory(token_expiration=3600)
    monkeypatch.setattr(manager, "_ensure_expiration_task", lambda: None)
    for i in range(1000):
        await manager.get_state(StateToken(ident=str(i), cls=dict))
    locks = Mock(wraps=manager._states_locks)
    monkeypatch.setattr(manager, "_states_locks", locks)

    assert manager._purge_expired_tokens() is not None
    assert locks.get.call_count <= 1


@pytest.fixture
def indexed_memory_manager(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[StateManagerMemory, Mock]:
    """Provide a manager whose deadlines are advanced without real sleeps.

    Args:
        monkeypatch: The pytest monkeypatch fixture.

    Returns:
        The manager and its controllable clock.
    """
    clock = Mock(return_value=1000.0)
    monkeypatch.setattr(memory, "time", SimpleNamespace(time=clock))
    manager = StateManagerMemory(token_expiration=10)
    monkeypatch.setattr(manager, "_ensure_expiration_task", lambda: None)
    return manager, clock


@pytest.mark.asyncio
async def test_memory_expiration_refresh_reorders_deadlines(
    indexed_memory_manager: tuple[StateManagerMemory, Mock],
):
    """Refreshes can move a deadline earlier or later without retaining old entries.

    Args:
        indexed_memory_manager: The manager and its controllable clock.
    """
    manager, clock = indexed_memory_manager
    tokens = [StateToken(ident=str(i), cls=dict) for i in range(3)]
    for i, token in enumerate(tokens):
        clock.return_value = 1000.0 + i
        await manager.get_state(token)

    clock.return_value = 1005.0
    await manager.get_state(tokens[0])
    manager.token_expiration = 1
    await manager.get_state(tokens[2])
    assert manager._purge_expired_tokens() == pytest.approx(1006.0)
    assert len(manager._expiration_heap) == 3

    for deadline, token, next_deadline in [
        (1006.0, tokens[2], 1011.0),
        (1011.0, tokens[1], 1015.0),
        (1015.0, tokens[0], None),
    ]:
        clock.return_value = deadline
        assert manager._purge_expired_tokens() == next_deadline
        assert token.cache_key not in manager.states
        assert token.cache_key not in manager._expiration_indices
    assert not manager._expiration_heap
    assert not manager._token_expires_at


@pytest.mark.asyncio
async def test_memory_expiration_skips_and_restores_locked_tokens(
    indexed_memory_manager: tuple[StateManagerMemory, Mock],
):
    """Held tokens survive expired deadlines and remain indexed after skipped scans.

    Args:
        indexed_memory_manager: The manager and its controllable clock.
    """
    manager, clock = indexed_memory_manager
    tokens = [StateToken(ident=str(i), cls=dict) for i in range(3)]
    locks = []
    for i, token in enumerate(tokens):
        clock.return_value = 1000.0 + i
        await manager.get_state(token)
        lock = await manager._get_state_lock(token)
        await lock.acquire()
        locks.append(lock)

    locks[2].release()
    assert manager._purge_expired_tokens() == pytest.approx(1012.0)
    assert len(manager._expiration_heap) == 3
    clock.return_value = 1020.0
    assert manager._purge_expired_tokens() is None
    assert set(manager.states) == {token.cache_key for token in tokens[:2]}
    assert len(manager._expiration_heap) == 2

    for lock in locks[:2]:
        lock.release()
    assert manager._purge_expired_tokens() is None
    assert not manager.states
    assert not manager._states_locks
    assert not manager._token_expires_at
    assert not manager._expiration_heap
    assert not manager._expiration_indices


@pytest.mark.asyncio
async def test_memory_expiration_index_stays_bounded_on_refresh(
    indexed_memory_manager: tuple[StateManagerMemory, Mock],
):
    """A frequently accessed session owns one deadline even at identical timestamps.

    Args:
        indexed_memory_manager: The manager and its controllable clock.
    """
    manager, clock = indexed_memory_manager
    tokens = [StateToken(ident=str(i), cls=dict) for i in range(100)]
    for token in tokens:
        await manager.get_state(token)
    for i in range(5000):
        # Repeated equal times exercise refreshes within one clock tick.
        clock.return_value = 1000.0 + i // 10
        await manager.get_state(tokens[i % len(tokens)])
    assert len(manager._expiration_heap) == len(tokens)
    assert len(manager._expiration_indices) == len(tokens)
    assert len(manager._token_expires_at) == len(tokens)


@pytest.mark.asyncio
async def test_memory_expiration_matches_scan_after_updates_and_removals(
    indexed_memory_manager: tuple[StateManagerMemory, Mock],
):
    """Indexed expiration matches a full-scan model across reordered deadlines.

    Args:
        indexed_memory_manager: The manager and its controllable clock.
    """
    manager, clock = indexed_memory_manager
    rng = random.Random(0)
    tokens = [StateToken(ident=str(i), cls=dict) for i in range(30)]
    expected: dict[str, float] = {}
    now = 1000.0
    for _ in range(500):
        now += rng.randrange(3)
        clock.return_value = now
        manager.token_expiration = rng.randrange(20)
        token = rng.choice(tokens)
        await manager.get_state(token)
        expected[token.cache_key] = now + manager.token_expiration
        if rng.randrange(3) == 0:
            expected = {key: expiry for key, expiry in expected.items() if expiry > now}
            assert manager._purge_expired_tokens() == min(
                expected.values(), default=None
            )
            assert set(manager.states) == set(expected)
        assert sorted(manager._expiration_heap) == sorted(
            (expiry, key) for key, expiry in expected.items()
        )
        assert manager._expiration_indices == {
            key: index for index, (_, key) in enumerate(manager._expiration_heap)
        }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "shape",
    ["bulk_due", "half_due", "all_held_due", "held_and_future", "all_held_future"],
)
async def test_memory_expiration_bounds_heap_work_for_batches(
    indexed_memory_manager: tuple[StateManagerMemory, Mock],
    monkeypatch: pytest.MonkeyPatch,
    shape: str,
):
    """Coalesced or held deadlines cannot require a heap repair per retained token.

    Args:
        indexed_memory_manager: The manager and its controllable clock.
        monkeypatch: The pytest monkeypatch fixture.
        shape: The distribution of due and held deadlines.
    """
    manager, clock = indexed_memory_manager
    count = 256
    expected = set()
    for i in range(count):
        future = (shape in {"half_due", "held_and_future"} and i >= count // 2) or (
            shape == "all_held_future"
        )
        held = shape in {"all_held_due", "all_held_future"} or (
            shape == "held_and_future" and i < count // 2
        )
        clock.return_value = 1000.0 + (20 if future else 0)
        token = StateToken(ident=str(i), cls=dict)
        await manager.get_state(token)
        if held:
            lock = await manager._get_state_lock(token)
            await lock.acquire()
        if future or held:
            expected.add(token.cache_key)
    clock.return_value = 1011.0
    repair = Mock(wraps=manager._sift_expiration)
    monkeypatch.setattr(manager, "_sift_expiration", repair)

    deadline = manager._purge_expired_tokens()

    assert deadline == (1030 if shape in {"half_due", "held_and_future"} else None)
    assert set(manager.states) == expected
    assert repair.call_count <= count // count.bit_length()
    assert len(manager._expiration_heap) == len(expected)
    assert manager._expiration_indices == {
        key: index for index, (_, key) in enumerate(manager._expiration_heap)
    }
    # A rebuilt heap must retain skipped held tokens for a subsequent unlock.
    for lock in manager._states_locks.values():
        if lock.locked():
            lock.release()
    clock.return_value = 1040.0
    assert manager._purge_expired_tokens() is None
    assert not manager._expiration_heap
    assert not manager._expiration_indices
    assert not manager._token_expires_at
    assert not manager.states
