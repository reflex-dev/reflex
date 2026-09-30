"""Unit tests for scripts/blockbuster_audit.py (the event-loop blocking audit)."""

import os
from pathlib import Path

import pytest

from scripts import blockbuster_audit


def test_isolate_db_keeps_the_cwd_database(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """The audit database lives under the root; a reflex.db in the cwd survives.

    Args:
        tmp_path: A temporary directory.
        monkeypatch: The pytest monkeypatch fixture.
    """
    cwd, root = tmp_path / "cwd", tmp_path / "root"
    cwd.mkdir()
    root.mkdir()
    monkeypatch.chdir(cwd)
    (cwd / "reflex.db").write_text("user data")
    (root / "reflex.db").write_text("previous audit")
    for name in ("REFLEX_DB_URL", "REFLEX_ASYNC_DB_URL"):
        # setenv first so monkeypatch also removes the value the helper sets.
        monkeypatch.setenv(name, "")
        monkeypatch.delenv(name)

    db_path = blockbuster_audit._isolate_db(root)

    assert db_path == (root / "reflex.db").resolve()
    assert not db_path.exists()
    assert (cwd / "reflex.db").read_text() == "user data"
    assert os.environ["REFLEX_DB_URL"] == f"sqlite:///{db_path.as_posix()}"
    assert (
        os.environ["REFLEX_ASYNC_DB_URL"] == f"sqlite+aiosqlite:///{db_path.as_posix()}"
    )
