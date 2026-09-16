"""Tests for the disk state manager."""

import math
import os
from pathlib import Path

import pytest

from reflex.istate.manager.disk import StateManagerDisk
from reflex.istate.manager.token import BaseStateToken, StateToken
from reflex.state import BaseState
from reflex.utils import prerequisites


class DiskPersistState(BaseState):
    """A state for testing disk persistence."""

    num: float = 3.15


def test_states_directory_survives_chdir(tmp_path: Path, monkeypatch):
    """The states directory must not move when the process cwd changes.

    Args:
        tmp_path: A temporary directory.
        monkeypatch: The pytest monkeypatch fixture.
    """
    app_dir = tmp_path / "app"
    app_dir.mkdir()
    monkeypatch.chdir(app_dir)
    manager = StateManagerDisk()
    states_dir = manager.states_directory
    assert states_dir.is_absolute()
    assert states_dir.is_dir()

    os.chdir(tmp_path)
    assert manager.states_directory == states_dir
    # Purge resolves against the original directory, not the new cwd.
    manager._purge_expired_states()


@pytest.mark.asyncio
async def test_debounced_set_state_flushes_latest_value(tmp_path, monkeypatch):
    """Test that debounced writes flush the latest queued value.

    Args:
        tmp_path: A temporary directory.
        monkeypatch: The pytest monkeypatch fixture.
    """
    monkeypatch.setattr(prerequisites, "get_states_dir", lambda: tmp_path)
    state_manager = StateManagerDisk(_write_debounce_seconds=60)
    token = StateToken(ident="client", cls=int)

    await state_manager.set_state(token, 1)
    first_item = state_manager._write_queue[token]
    await state_manager.set_state(token, 2)

    assert state_manager._write_queue[token] is first_item
    assert first_item.state == 2

    await state_manager.close()

    fresh_state_manager = StateManagerDisk(_write_debounce_seconds=0)
    assert await fresh_state_manager.get_state(token) == 2
    await fresh_state_manager.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("write_debounce_seconds", [0, 60])
async def test_set_state_updates_cache_for_arbitrary_instance(
    tmp_path, monkeypatch, write_debounce_seconds
):
    """Test that set_state replaces a cached state with the supplied instance.

    Args:
        tmp_path: A temporary directory.
        monkeypatch: The pytest monkeypatch fixture.
        write_debounce_seconds: The debounce interval under test.
    """
    monkeypatch.setattr(prerequisites, "get_states_dir", lambda: tmp_path)
    state_manager = StateManagerDisk(_write_debounce_seconds=write_debounce_seconds)
    token = StateToken(ident="client", cls=dict)
    cached_state = await state_manager.get_state(token)
    state = {"value": 2}

    assert state is not cached_state

    await state_manager.set_state(token, state)

    assert state_manager.states[token.cache_key] is state
    assert token.cache_key in state_manager._token_last_touched
    if write_debounce_seconds > 0:
        assert state_manager._write_queue[token].state is state

    await state_manager.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("write_debounce_seconds", [0, 60])
async def test_set_state_persists_untouched_base_state(
    tmp_path, monkeypatch, write_debounce_seconds
):
    """Test that explicitly supplied untouched BaseState values are persisted.

    Args:
        tmp_path: A temporary directory.
        monkeypatch: The pytest monkeypatch fixture.
        write_debounce_seconds: The debounce interval under test.
    """
    monkeypatch.setattr(prerequisites, "get_states_dir", lambda: tmp_path)
    state_manager = StateManagerDisk(_write_debounce_seconds=write_debounce_seconds)
    token = BaseStateToken(ident="client", cls=DiskPersistState)
    state = DiskPersistState(_reflex_internal_init=True)  # pyright: ignore [reportCallIssue]
    object.__setattr__(state, "num", 9.5)
    state.dirty_vars.clear()
    state._was_touched = False

    await state_manager.set_state(token, state)
    await state_manager.close()

    fresh_state_manager = StateManagerDisk(_write_debounce_seconds=0)
    persisted_state = await fresh_state_manager.get_state(token)
    assert isinstance(persisted_state, DiskPersistState)
    assert math.isclose(persisted_state.num, 9.5)
    await fresh_state_manager.close()
