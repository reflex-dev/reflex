"""Tests for state manager token expiration."""

import asyncio
import time
from collections.abc import AsyncGenerator, Callable

import pytest
import pytest_asyncio

from reflex.istate.manager.memory import StateManagerMemory
from reflex.istate.manager.token import BaseStateToken
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


@pytest_asyncio.fixture(loop_scope="function", scope="function")
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
