"""Tests for the disk state manager."""

import asyncio
import math
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from reflex_base.constants import Env
from reflex_base.environment import environment
from reflex_base.vars.base import computed_var

from reflex.istate.manager import disk
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


async def test_idle_write_queue_scans_only_when_files_can_expire(tmp_path, monkeypatch):
    """Idle queue ticks skip unexpired files but still purge at their deadline."""
    now = [1000.0]
    monkeypatch.setattr(disk, "time", SimpleNamespace(time=lambda: now[0]))
    monkeypatch.setattr(disk.prerequisites, "get_states_dir", lambda: tmp_path)
    state_file = tmp_path / "session.pkl"
    state_file.touch()
    os.utime(state_file, (950, 950))
    manager = StateManagerDisk(token_expiration=100)
    listing = Mock(wraps=disk.path_ops.ls)
    monkeypatch.setattr(disk.path_ops, "ls", listing)
    ticks = iter([1002, 1049, 1051])

    async def advance():
        await asyncio.sleep(0)
        assert state_file.exists() == (now[0] <= 1050)
        if (next_tick := next(ticks, None)) is None:
            raise asyncio.CancelledError
        now[0] = next_tick

    monkeypatch.setattr(manager, "_process_write_queue_delay", advance)
    with pytest.raises(asyncio.CancelledError):
        await manager._process_write_queue()
    assert listing.call_count == 1


@pytest.fixture
def disk_clock(tmp_path, monkeypatch):
    """Control disk deadlines without changing the process-wide clock.

    Returns:
        A list containing the current disk-manager timestamp.
    """
    now = [1000.0]
    monkeypatch.setattr(disk, "time", SimpleNamespace(time=lambda: now[0]))
    monkeypatch.setattr(disk.prerequisites, "get_states_dir", lambda: tmp_path)
    return now


async def test_new_files_after_empty_scan_expire(tmp_path, monkeypatch, disk_clock):
    """An empty scan cannot postpone discovery beyond one token lifetime."""
    manager = StateManagerDisk(token_expiration=100)
    state_file = tmp_path / "later.pkl"
    state_file.touch()
    os.utime(state_file, (1001, 1001))
    listing = Mock(wraps=disk.path_ops.ls)
    monkeypatch.setattr(disk.path_ops, "ls", listing)

    disk_clock[0] = 1002
    await manager._maybe_purge_expired_states()
    listing.assert_not_called()
    disk_clock[0] = 1100
    await manager._maybe_purge_expired_states()
    assert state_file.exists()
    disk_clock[0] = 1102
    await manager._maybe_purge_expired_states()
    assert not state_file.exists()
    assert listing.call_count == 2


@pytest.mark.parametrize("lifetime", [5, 200])
async def test_disk_expiration_lifetime_changes(tmp_path, disk_clock, lifetime):
    """Changing the lifetime invalidates deadlines from the previous setting."""
    state_file = tmp_path / "existing.pkl"
    state_file.touch()
    os.utime(state_file, (990, 990))
    manager = StateManagerDisk(token_expiration=100)
    manager.token_expiration = lifetime

    await manager._maybe_purge_expired_states()
    assert state_file.exists() == (lifetime == 200)
    disk_clock[0] = 1191
    await manager._maybe_purge_expired_states()
    assert not state_file.exists()


async def test_disk_write_keeps_expiration_deadline(monkeypatch, disk_clock):
    """A write skips rescanning, and the written file still expires on schedule."""
    manager = StateManagerDisk(token_expiration=100)
    listing = Mock(wraps=disk.path_ops.ls)
    monkeypatch.setattr(disk.path_ops, "ls", listing)
    token = StateToken(ident="written", cls=dict)
    disk_clock[0] = 1050
    await manager.set_state_for_substate(token, {"count": 1})
    state_file = manager.token_path(token)
    os.utime(state_file, (1050, 1050))

    disk_clock[0] = 1060
    await manager._maybe_purge_expired_states()
    listing.assert_not_called()
    disk_clock[0] = 1100
    await manager._maybe_purge_expired_states()
    assert state_file.exists()
    disk_clock[0] = 1151
    await manager._maybe_purge_expired_states()
    assert not state_file.exists()
    assert listing.call_count == 2


async def test_disk_expiration_lifetime_changes_while_scan_dispatched(
    tmp_path, monkeypatch, disk_clock
):
    """A deadline is associated with the lifetime actually used by the worker."""
    state_file = tmp_path / "changed-lifetime.pkl"
    state_file.touch()
    os.utime(state_file, (990, 990))
    manager = StateManagerDisk(token_expiration=100)
    manager._next_disk_purge = 0

    async def scan_with_temporary_lifetime(fn):
        await asyncio.sleep(0)
        manager.token_expiration = 200
        result = fn()
        manager.token_expiration = 100
        return result

    with monkeypatch.context() as patch:
        patch.setattr(disk, "run_in_thread", scan_with_temporary_lifetime)
        await manager._maybe_purge_expired_states()

    disk_clock[0] = 1091
    await manager._maybe_purge_expired_states()
    assert not state_file.exists()


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
async def test_set_state_for_substate_builds_tokens_for_written_states_only(
    tmp_path, monkeypatch
):
    """Writing a tree derives a token only for the states that are written.

    Args:
        tmp_path: A temporary directory.
        monkeypatch: The pytest monkeypatch fixture.
    """
    monkeypatch.setattr(prerequisites, "get_states_dir", lambda: tmp_path)

    class DiskTreeParent(BaseState):
        value: int = 0

    class DiskTreeFirst(DiskTreeParent):
        value_first: int = 0

    class DiskTreeSecond(DiskTreeParent):
        value_second: int = 0

    state_manager = StateManagerDisk(_write_debounce_seconds=0)
    token = BaseStateToken(ident="client", cls=DiskTreeParent)
    state = await state_manager.get_state(token)
    assert isinstance(state, DiskTreeParent)
    assert len(state.substates) == 2
    state.substates[DiskTreeFirst.get_name()].value_first = 1  # pyright: ignore [reportAttributeAccessIssue]

    written: list[type[BaseState]] = []
    with_cls = BaseStateToken.with_cls

    def recording_with_cls(self, cls):
        written.append(cls)
        return with_cls(self, cls)

    with monkeypatch.context() as patch:
        patch.setattr(BaseStateToken, "with_cls", recording_with_cls)
        await state_manager.set_state_for_substate(token, state)

    assert written == [DiskTreeFirst]
    await state_manager.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("env_mode", "hot_reload", "after_reload"),
    [
        (Env.DEV, True, ["a"]),
        (Env.DEV, False, ["a", "b"]),
        (Env.PREVIEW, True, ["a", "b"]),
        (Env.PROD, False, ["a", "b"]),
    ],
)
async def test_states_from_disk_recompute_cached_vars(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    env_mode: Env,
    hot_reload: bool,
    after_reload: list[str],
):
    """Under the dev hot reloader, states read back from disk recompute cached vars.

    A state is only read from disk when it is not in memory, as after a hot
    reload, which may have changed what the computed vars return. The fields
    keep their values. Outside a dev hot reloader the cache is kept.

    Args:
        tmp_path: A temporary directory.
        monkeypatch: The pytest monkeypatch fixture.
        env_mode: The mode the app runs in.
        hot_reload: Whether the backend runs under the dev hot reloader.
        after_reload: The cached var value expected after the reload.
    """
    monkeypatch.setattr(prerequisites, "get_states_dir", lambda: tmp_path)
    monkeypatch.setenv("REFLEX_ENV_MODE", env_mode.value)
    monkeypatch.setenv(
        environment.REFLEX_DEV_BACKEND_RELOAD_ACTIVE.name, str(hot_reload)
    )
    rows = ["a", "b"]

    class DiskCachedState(BaseState):
        count: int = 0

        @computed_var(cache=True)
        def data(self) -> list[str]:
            """The rows, which a reload can change.

            Returns:
                A copy of the rows.
            """
            return list(rows)

    class DiskCachedChild(DiskCachedState):
        @computed_var(cache=True)
        def child_data(self) -> list[str]:
            """The rows, cached on the substate.

            Returns:
                A copy of the rows.
            """
            return list(rows)

    token = BaseStateToken(ident="client", cls=DiskCachedState)
    state_manager = StateManagerDisk(_write_debounce_seconds=0)
    async with state_manager.modify_state(token) as state:
        assert isinstance(state, DiskCachedState)
        state.count = 99
        child = await state.get_state(DiskCachedChild)
        assert (state.data, child.child_data) == (["a", "b"], ["a", "b"])
    rows[:] = ["a"]
    # A state still in memory keeps its cached values.
    assert await state_manager.get_state(token) is state
    assert state.data == ["a", "b"]
    await state_manager.close()

    reloaded_state_manager = StateManagerDisk(_write_debounce_seconds=0)
    state = await reloaded_state_manager.get_state(token)
    assert isinstance(state, DiskCachedState)
    child = await state.get_state(DiskCachedChild)
    assert (state.count, state.data, child.child_data) == (
        99,
        after_reload,
        after_reload,
    )
    await reloaded_state_manager.close()
