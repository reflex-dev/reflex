"""Tests for the disk state manager."""

import asyncio
import builtins
import io
import math
import os
import threading
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


@pytest.mark.asyncio
async def test_state_files_are_not_touched_on_the_event_loop(
    tmp_path: Path, monkeypatch, token: str
):
    """Reading and writing state files must happen in a worker thread.

    Args:
        tmp_path: A temporary directory.
        monkeypatch: The pytest monkeypatch fixture.
        token: A token.
    """
    monkeypatch.chdir(tmp_path)
    loop_thread = threading.get_ident()
    on_loop: list[tuple[str, str]] = []

    def _watch(module, name: str):
        original = getattr(module, name)

        def wrapper(path, *args, **kwargs):
            if threading.get_ident() == loop_thread and str(path).startswith(
                str(tmp_path)
            ):
                on_loop.append((name, str(path)))
            return original(path, *args, **kwargs)

        monkeypatch.setattr(module, name, wrapper)

    class Root(BaseState):
        pass

    class Child(Root):
        num: int = 0

    # Construction creates the directory synchronously; that is startup work.
    writer, reader = StateManagerDisk(), StateManagerDisk()
    for module, name in ((io, "open"), (builtins, "open"), (os, "stat"), (os, "mkdir")):
        _watch(module, name)

    bs_token = BaseStateToken(ident=token, cls=Root)
    async with writer.modify_state(bs_token) as root:
        (await root.get_state(Child)).num = 1
    await writer.close()

    root = await reader.get_state(bs_token)
    assert (await root.get_state(Child)).num == 1
    await reader.close()

    assert on_loop == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "state_token",
    [
        BaseStateToken(ident="client", cls=DiskPersistState),
        StateToken(ident="client", cls=dict),
    ],
    ids=["base_state", "plain"],
)
async def test_get_state_keeps_state_cached_during_its_disk_read(
    tmp_path: Path, monkeypatch, state_token: StateToken
):
    """A get_state that missed the cache must not replace a state cached meanwhile.

    The disk read yields to the event loop, so an unlocked reader can finish
    after a locked modify_state has cached and changed the same state.

    Args:
        tmp_path: A temporary directory.
        monkeypatch: The pytest monkeypatch fixture.
        state_token: The token under test.
    """
    monkeypatch.setattr(prerequisites, "get_states_dir", lambda: tmp_path)
    state_manager = StateManagerDisk(_write_debounce_seconds=60)
    load_state = state_manager.load_state
    reader_parked = asyncio.Event()
    release_reader = asyncio.Event()

    async def gated_load_state(token: StateToken):
        loaded = await load_state(token)
        if asyncio.current_task() is reader:
            # Hold the reader inside its disk read while the locked modify runs.
            reader_parked.set()
            await release_reader.wait()
        return loaded

    monkeypatch.setattr(state_manager, "load_state", gated_load_state)
    reader = asyncio.create_task(state_manager.get_state(state_token))
    await reader_parked.wait()

    async with state_manager.modify_state(state_token) as state:
        pass
    release_reader.set()

    # The reader drops its stale copy, so the modified instance stays cached.
    assert await reader is state
    assert state_manager.states[state_token.cache_key] is state
    await state_manager.close()
