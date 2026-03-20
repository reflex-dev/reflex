"""Tests for state manager token expiration."""

import asyncio
import time
from collections.abc import AsyncGenerator, Callable

import pytest
import pytest_asyncio

from reflex.istate.manager.memory import StateManagerMemory
from reflex.state import BaseState, _substate_key


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


@pytest_asyncio.fixture(loop_scope="function", scope="function")
async def state_manager_memory() -> AsyncGenerator[StateManagerMemory]:
    """Create a memory state manager with a short expiration.

    Yields:
        The memory state manager under test.
    """
    state_manager = StateManagerMemory(state=ExpiringState, token_expiration=1)
    yield state_manager
    await state_manager.close()


@pytest.mark.asyncio
async def test_memory_state_manager_evicts_expired_state(
    state_manager_memory: StateManagerMemory,
    token: str,
):
    """Expired states should be removed from the in-memory cache and locks."""
    state_token = _substate_key(token, ExpiringState)

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
    state_token = _substate_key(token, ExpiringState)
    state = await state_manager_memory.get_state(state_token)
    assert isinstance(state, ExpiringState)
    state.value = 7
    first_expires_at = state_manager_memory._token_expires_at[token]

    await asyncio.sleep(0.6)

    same_state = await state_manager_memory.get_state(state_token)
    assert same_state is state
    assert state_manager_memory._token_expires_at[token] > first_expires_at

    await asyncio.sleep(0.6)

    assert token in state_manager_memory.states
    assert state_manager_memory.states[token] is state


@pytest.mark.asyncio
async def test_memory_state_manager_set_state_refreshes_expiration(
    state_manager_memory: StateManagerMemory,
    token: str,
):
    """Persisting a state should extend its expiration window."""
    state_token = _substate_key(token, ExpiringState)
    state = await state_manager_memory.get_state(state_token)
    assert isinstance(state, ExpiringState)
    state.value = 17
    first_expires_at = state_manager_memory._token_expires_at[token]

    await asyncio.sleep(0.6)

    await state_manager_memory.set_state(state_token, state)

    assert state_manager_memory._token_expires_at[token] > first_expires_at

    await asyncio.sleep(0.6)

    assert token in state_manager_memory.states
    assert state_manager_memory.states[token] is state


@pytest.mark.asyncio
async def test_memory_state_manager_multiple_touches_do_not_evict_early(
    state_manager_memory: StateManagerMemory,
    token: str,
):
    """Repeated touches should honor the latest expiration deadline."""
    state_token = _substate_key(token, ExpiringState)
    state = await state_manager_memory.get_state(state_token)
    assert isinstance(state, ExpiringState)

    for _ in range(3):
        await asyncio.sleep(0.35)
        assert await state_manager_memory.get_state(state_token) is state

    # The first deadlines have passed, but the latest touch should still keep the
    # token alive until its own expiration window ends.
    await asyncio.sleep(0.2)

    assert token in state_manager_memory.states

    await _poll_until(lambda: token not in state_manager_memory.states)


@pytest.mark.asyncio
async def test_memory_state_manager_returns_fresh_state_after_eviction(
    state_manager_memory: StateManagerMemory,
    token: str,
):
    """A token should get a fresh state after the previous one expires."""
    state_token = _substate_key(token, ExpiringState)
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
    await state_manager_memory.get_state(_substate_key(token, ExpiringState))

    expiration_task = state_manager_memory._expiration_task
    assert expiration_task is not None
    assert not expiration_task.done()

    await state_manager_memory.close()

    assert state_manager_memory._expiration_task is None
    assert expiration_task.done()

    await state_manager_memory.close()


@pytest.mark.asyncio
async def test_memory_state_manager_evicts_expired_locked_state_after_unlock(
    state_manager_memory: StateManagerMemory,
    token: str,
):
    """An expired locked state should be evicted once its lock is released."""
    state_token = _substate_key(token, ExpiringState)

    async with state_manager_memory.modify_state(state_token) as state:
        state.value = 5
        await _poll_until(
            lambda: token in state_manager_memory._pending_locked_expirations,
            timeout=2.0,
        )
        assert token in state_manager_memory.states

    await _poll_until(lambda: token not in state_manager_memory.states)
