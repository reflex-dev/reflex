"""Tests for the disk state manager."""

import os
from pathlib import Path

from reflex.istate.manager.disk import StateManagerDisk


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
