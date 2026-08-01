"""Tests for state manager lock isolation."""

import asyncio
from collections.abc import Callable
from typing import Protocol

import pytest

from reflex.istate.manager.disk import StateManagerDisk
from reflex.istate.manager.memory import StateManagerMemory
from reflex.istate.manager.redis import StateManagerRedis
from tests.units.mock_redis import mock_redis


class StateManagerWithLock(Protocol):
    """State manager protocol exposing the internal manager lock."""

    _state_manager_lock: asyncio.Lock


@pytest.mark.parametrize(
    "state_manager_factory",
    [
        pytest.param(StateManagerMemory, id="memory"),
        pytest.param(StateManagerDisk, id="disk"),
        pytest.param(lambda: StateManagerRedis(redis=mock_redis()), id="redis"),
    ],
)
def test_state_manager_lock_is_instance_local(
    state_manager_factory: Callable[[], StateManagerWithLock],
):
    """Each state manager instance should own its manager lock."""
    first = state_manager_factory()
    second = state_manager_factory()

    assert first._state_manager_lock is not second._state_manager_lock
