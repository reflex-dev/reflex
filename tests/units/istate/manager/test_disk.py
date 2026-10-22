"""Tests for the disk state manager."""

import logging
import math
import os
import pickle
from pathlib import Path

import pytest

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
async def test_load_state_missing_file_is_not_logged(tmp_path, monkeypatch, caplog):
    """A state that was never persisted loads as None without logging.

    Args:
        tmp_path: A temporary directory.
        monkeypatch: The pytest monkeypatch fixture.
        caplog: The pytest log capture fixture.
    """
    monkeypatch.setattr(prerequisites, "get_states_dir", lambda: tmp_path)
    state_manager = StateManagerDisk(_write_debounce_seconds=0)
    token = StateToken(ident="client", cls=int)

    with caplog.at_level(logging.DEBUG, logger=disk.__name__):
        assert await state_manager.load_state(token) is None

    assert not caplog.records
    await state_manager.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("token", "contents", "fresh_state"),
    [
        (StateToken(ident="client", cls=int), b"not-a-pickle", 0),
        (StateToken(ident="client", cls=int), b"", 0),
        (BaseStateToken(ident="client", cls=DiskPersistState), b"not-a-pickle", None),
        (BaseStateToken(ident="client", cls=DiskPersistState), b"", None),
    ],
)
async def test_load_state_logs_unreadable_file(
    tmp_path, monkeypatch, caplog, token, contents, fresh_state
):
    """A persisted state file that is damaged is logged as a warning.

    Args:
        tmp_path: A temporary directory.
        monkeypatch: The pytest monkeypatch fixture.
        caplog: The pytest log capture fixture.
        token: The token whose state file is damaged.
        contents: The damaged file contents.
        fresh_state: The expected fresh state, or None for a DiskPersistState.
    """
    monkeypatch.setattr(prerequisites, "get_states_dir", lambda: tmp_path)
    state_manager = StateManagerDisk(_write_debounce_seconds=0)
    token_path = state_manager.token_path(token)
    token_path.write_bytes(contents)

    with caplog.at_level(logging.DEBUG, logger=disk.__name__):
        assert await state_manager.load_state(token) is None

    [record] = caplog.records
    assert record.levelno == logging.WARNING
    assert str(token_path) in record.getMessage()
    assert record.exc_info is not None

    caplog.clear()
    with caplog.at_level(logging.WARNING, logger=disk.__name__):
        state = await state_manager.get_state(token)
    assert [r.levelno for r in caplog.records] == [logging.WARNING]
    if fresh_state is None:
        assert isinstance(state, DiskPersistState)
        assert math.isclose(state.num, 3.15)
    else:
        assert state == fresh_state
    await state_manager.close()


@pytest.mark.asyncio
async def test_load_state_logs_schema_mismatch_at_debug(tmp_path, monkeypatch, caplog):
    """A persisted BaseState whose class changed since it was written is logged at debug.

    Args:
        tmp_path: A temporary directory.
        monkeypatch: The pytest monkeypatch fixture.
        caplog: The pytest log capture fixture.
    """
    monkeypatch.setattr(prerequisites, "get_states_dir", lambda: tmp_path)
    state_manager = StateManagerDisk(_write_debounce_seconds=0)
    token = BaseStateToken(ident="client", cls=DiskPersistState)
    token_path = state_manager.token_path(token)
    stale_state = DiskPersistState(_reflex_internal_init=True)  # pyright: ignore [reportCallIssue]
    stale_state.num = 9.5
    token_path.write_bytes(pickle.dumps(("stale-schema", stale_state)))

    with caplog.at_level(logging.DEBUG, logger=disk.__name__):
        assert await state_manager.load_state(token) is None

    [record] = caplog.records
    assert record.levelno == logging.DEBUG
    assert str(token_path) in record.getMessage()

    state = await state_manager.get_state(token)
    assert isinstance(state, DiskPersistState)
    assert math.isclose(state.num, 3.15)
    await state_manager.close()
