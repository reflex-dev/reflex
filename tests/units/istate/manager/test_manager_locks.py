"""Tests for state manager lock isolation."""

import asyncio
from collections.abc import Callable
from pathlib import Path
from typing import Protocol

import pytest

from reflex.istate.manager.disk import StateManagerDisk
from reflex.istate.manager.memory import StateManagerMemory
from reflex.istate.manager.redis import StateManagerRedis
from reflex.utils import prerequisites
from tests.units.mock_redis import mock_redis


class StateManagerWithLock(Protocol):
    """State manager protocol exposing the internal manager lock."""

    _state_manager_lock: asyncio.Lock


def _memory_state_manager_factory(
    _: Path, __: pytest.MonkeyPatch
) -> Callable[[], StateManagerMemory]:
    """Create in-memory state managers.

    Returns:
        A factory for in-memory state managers.
    """
    return StateManagerMemory


def _disk_state_manager_factory(
    states_directory: Path, monkeypatch: pytest.MonkeyPatch
) -> Callable[[], StateManagerDisk]:
    """Create disk state managers isolated to a temporary states directory.

    Args:
        states_directory: The temporary directory for disk state files.
        monkeypatch: Pytest monkeypatch fixture.

    Returns:
        A factory for isolated disk state managers.
    """
    monkeypatch.setattr(prerequisites, "get_states_dir", lambda: states_directory)
    return StateManagerDisk


def _redis_state_manager_factory(
    _: Path, __: pytest.MonkeyPatch
) -> Callable[[], StateManagerRedis]:
    """Create redis state managers backed by mock redis.

    Returns:
        A factory for redis state managers.
    """
    return lambda: StateManagerRedis(redis=mock_redis())


@pytest.mark.parametrize(
    "state_manager_factory_factory",
    [
        pytest.param(_memory_state_manager_factory, id="memory"),
        pytest.param(_disk_state_manager_factory, id="disk"),
        pytest.param(_redis_state_manager_factory, id="redis"),
    ],
)
def test_state_manager_lock_is_instance_local(
    state_manager_factory_factory: Callable[
        [Path, pytest.MonkeyPatch], Callable[[], StateManagerWithLock]
    ],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    """Each state manager instance should own its manager lock."""
    state_manager_factory = state_manager_factory_factory(tmp_path, monkeypatch)
    first = state_manager_factory()
    second = state_manager_factory()

    assert first._state_manager_lock is not second._state_manager_lock
