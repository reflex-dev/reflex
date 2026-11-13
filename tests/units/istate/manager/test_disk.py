"""Tests for the disk state manager."""

import asyncio
import contextlib
import math
import os
from pathlib import Path

import pytest
from reflex_base.constants import Env
from reflex_base.environment import environment
from reflex_base.vars.base import computed_var

from reflex.istate.manager.disk import StateManagerDisk
from reflex.istate.manager.token import BaseStateToken, StateToken
from reflex.state import BaseState
from reflex.utils import prerequisites


class DiskPersistState(BaseState):
    """A state for testing disk persistence."""

    num: float = 3.15


class DiskFailureRoot(BaseState):
    """A state whose handler fails, written as a tree.

    A substate rides along so the failure path covers the whole tree, not just
    the state the token names.
    """

    num: float = 0.0


class DiskFailureChild(DiskFailureRoot):
    """A substate written alongside its failed handler's root state."""

    child_value: str = ""


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


@pytest.mark.asyncio
@pytest.mark.parametrize("write_debounce_seconds", [0, 60])
async def test_modify_exception_persists_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, write_debounce_seconds: int
):
    """Keep the writes of a handler that raises, like the other state managers.

    Args:
        tmp_path: A temporary directory.
        monkeypatch: The pytest monkeypatch fixture.
        write_debounce_seconds: The debounce interval under test.
    """
    monkeypatch.setattr(prerequisites, "get_states_dir", lambda: tmp_path)
    state_manager = StateManagerDisk(_write_debounce_seconds=write_debounce_seconds)
    token = BaseStateToken(ident="client", cls=DiskPersistState)

    with pytest.raises(RuntimeError, match="handler failed"):
        async with state_manager.modify_state(token) as state:
            assert isinstance(state, DiskPersistState)
            state.num = 1.5
            msg = "handler failed"
            raise RuntimeError(msg)

    await state_manager.close()

    # A manager that starts from the directory alone must see the write.
    fresh_state_manager = StateManagerDisk(_write_debounce_seconds=0)
    persisted_state = await fresh_state_manager.get_state(token)
    assert isinstance(persisted_state, DiskPersistState)
    assert math.isclose(persisted_state.num, 1.5)
    await fresh_state_manager.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("write_debounce_seconds", [0, 60])
async def test_modify_cancelled_persists_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, write_debounce_seconds: int
):
    """Keep mutations and cancellation cleanup visible to the next read from disk.

    Args:
        tmp_path: A temporary directory.
        monkeypatch: The pytest monkeypatch fixture.
        write_debounce_seconds: The debounce interval under test.
    """
    monkeypatch.setattr(prerequisites, "get_states_dir", lambda: tmp_path)
    state_manager = StateManagerDisk(_write_debounce_seconds=write_debounce_seconds)
    token = BaseStateToken(ident="client", cls=DiskFailureRoot)
    started = asyncio.Event()

    async def modify():
        """Mutate state before cancellation and again during handler cleanup."""
        async with state_manager.modify_state(token) as state:
            assert isinstance(state, DiskFailureRoot)
            state.num = 1.0
            child = state.substates[DiskFailureChild.get_name()]
            assert isinstance(child, DiskFailureChild)
            child.child_value = "cancelled"
            started.set()
            try:
                await asyncio.Event().wait()
            finally:
                state.num = 2.0

    task = asyncio.create_task(modify())
    await asyncio.wait_for(started.wait(), timeout=5)
    task.cancel("superseded")
    with pytest.raises(asyncio.CancelledError, match="superseded"):
        await task

    await state_manager.close()

    # A manager that starts from the directory alone must see the whole tree.
    fresh_state_manager = StateManagerDisk(_write_debounce_seconds=0)
    persisted_state = await fresh_state_manager.get_state(token)
    assert isinstance(persisted_state, DiskFailureRoot)
    assert math.isclose(persisted_state.num, 2.0)
    persisted_child = persisted_state.substates[DiskFailureChild.get_name()]
    assert isinstance(persisted_child, DiskFailureChild)
    assert persisted_child.child_value == "cancelled"
    await fresh_state_manager.close()


@pytest.mark.asyncio
async def test_repeated_cancellation_waits_for_state_save(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """Keep the state lock until a repeatedly cancelled handler finishes saving.

    Args:
        tmp_path: A temporary directory.
        monkeypatch: The pytest monkeypatch fixture.
    """
    monkeypatch.setattr(prerequisites, "get_states_dir", lambda: tmp_path)
    state_manager = StateManagerDisk(_write_debounce_seconds=0)
    token = BaseStateToken(ident="client", cls=DiskPersistState)
    started = asyncio.Event()
    saving = asyncio.Event()
    release_save = asyncio.Event()
    original_set_state = state_manager.set_state

    async def save(*args, **kwargs):
        """Pause the state write while the handler is cancelled again.

        Args:
            args: The positional arguments for the real set_state.
            kwargs: The keyword arguments for the real set_state.
        """
        saving.set()
        await release_save.wait()
        await original_set_state(*args, **kwargs)

    monkeypatch.setattr(state_manager, "set_state", save)

    async def modify():
        """Mutate state and suspend until superseded."""
        async with state_manager.modify_state(token) as state:
            assert isinstance(state, DiskPersistState)
            state.num = 1.5
            started.set()
            await asyncio.Event().wait()

    task = asyncio.create_task(modify())
    try:
        await asyncio.wait_for(started.wait(), timeout=5)
        task.cancel("superseded")
        await asyncio.wait_for(saving.wait(), timeout=5)
        for _ in range(2):
            task.cancel("shutdown")
            await asyncio.sleep(0)
        # Neither the save nor the lock may be abandoned to the new cancellation.
        assert not task.done()
        assert state_manager._is_locked(token)
        release_save.set()
        with pytest.raises(asyncio.CancelledError, match="superseded"):
            await task
        assert not state_manager._is_locked(token)
    finally:
        release_save.set()
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task

    await state_manager.close()
