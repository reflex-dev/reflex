"""Tests for the disk state manager."""

import math
import os
import subprocess
import sys
from pathlib import Path

import pytest
from reflex_base.vars.base import computed_var

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
async def test_states_from_disk_recompute_cached_vars(tmp_path, monkeypatch):
    """States read back from disk keep their fields but recompute cached vars.

    A state is only read from disk when it is not in memory, as after a hot
    reload, which may have changed what the computed vars return.

    Args:
        tmp_path: A temporary directory.
        monkeypatch: The pytest monkeypatch fixture.
    """
    monkeypatch.setattr(prerequisites, "get_states_dir", lambda: tmp_path)
    rows = ["a", "b"]

    class DiskCachedState(BaseState):
        count: int = 0

        @computed_var(cache=True)
        def data(self) -> list[str]:
            return list(rows)

    class DiskCachedChild(DiskCachedState):
        @computed_var(cache=True)
        def child_data(self) -> list[str]:
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
    assert (state.count, state.data, child.child_data) == (99, ["a"], ["a"])
    await reloaded_state_manager.close()


_HOT_RELOAD_APP = """
import reflex as rx
from reflex.state import BaseState

class HotState(BaseState):
    count: int = 7

    @rx.var(cache=True)
    def main_data(self) -> list[dict]:
        return {rows}
"""

_HOT_RELOAD_BACKEND = """
import asyncio
import sys

from hot_app import HotState
from reflex.istate.manager.disk import StateManagerDisk
from reflex.istate.manager.token import BaseStateToken


async def main():
    state_manager = StateManagerDisk(_write_debounce_seconds=0)
    token = BaseStateToken(ident="client", cls=HotState)
    if sys.argv[1] == "before":
        async with state_manager.modify_state(token) as state:
            state.count = 99
            print(state.main_data)
    else:
        state = await state_manager.get_state(token)
        print(state.count, state.main_data)
    await state_manager.close()


asyncio.run(main())
"""


def test_hot_reload_recomputes_cached_vars(tmp_path: Path):
    """A backend restarted after a getter edit returns the new value and keeps fields.

    Args:
        tmp_path: A temporary directory.
    """
    app = tmp_path / "hot_app.py"
    backend = tmp_path / "backend.py"
    backend.write_text(_HOT_RELOAD_BACKEND)

    def run(step: str) -> str:
        """Run one step of the backend script in a new process.

        Args:
            step: "before" or "after" the reload.

        Returns:
            What the script printed.
        """
        return subprocess.run(
            # -B: no bytecode cache, so the second run imports the edited app.
            [sys.executable, "-B", str(backend), step],
            capture_output=True,
            text=True,
            check=True,
            cwd=tmp_path,
        ).stdout.strip()

    app.write_text(_HOT_RELOAD_APP.format(rows='[{"id": "2"}, {"id": "3"}]'))
    assert run("before") == "[{'id': '2'}, {'id': '3'}]"
    # Only the getter changes, so the saved state still matches the schema.
    app.write_text(_HOT_RELOAD_APP.format(rows='[{"id": "2"}]'))
    assert run("after") == "99 [{'id': '2'}]"
