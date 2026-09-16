"""Tests for the disk state manager."""

import builtins
import io
import os
import threading
from pathlib import Path

import pytest

from reflex.istate.manager.disk import StateManagerDisk
from reflex.istate.manager.token import BaseStateToken
from reflex.state import BaseState


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
