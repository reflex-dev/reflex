"""Tests for the disk state manager."""

import asyncio
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from reflex.istate.manager import disk
from reflex.istate.manager.disk import StateManagerDisk
from reflex.istate.manager.token import StateToken


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
