"""Unit tests for scripts/blockbuster_audit.py (the event-loop blocking audit)."""

import os
from collections import defaultdict
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


def test_report_matches_repo_frames_by_resolved_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """Frames are matched to the repository by resolved path, not string prefix.

    Args:
        tmp_path: A temporary directory.
        monkeypatch: The pytest monkeypatch fixture.
    """
    repo = blockbuster_audit.REPO_ROOT
    # A relative pseudo-file must not resolve into the repo from a cwd inside it.
    monkeypatch.chdir(repo)
    frozen = ("<frozen runpy>", 1, "_run_code")
    findings = {
        "reflex": [
            frozen,
            (str(repo / "tests" / ".." / "reflex" / "state.py"), 10, "f"),
        ],
        "test": [(str(repo / "tests" / "units" / "test_state.py"), 20, "test_f")],
        "third": [frozen],
    }
    monkeypatch.setattr(blockbuster_audit, "_findings", {})
    monkeypatch.setattr(blockbuster_audit, "_counts", defaultdict(int))
    for name, frames in findings.items():
        key = (name, tuple((fn, func) for fn, _, func in frames))
        blockbuster_audit._findings[key] = frames
        blockbuster_audit._counts[key] = 1

    out = tmp_path / "report.txt"
    assert blockbuster_audit.report(out) == 3
    assert [
        line for line in out.read_text().splitlines() if line.startswith("===")
    ] == [
        "=== [REFLEX] reflex  x1  innermost: reflex/state.py:10 f",
        "=== [TEST] test  x1  innermost: tests/units/test_state.py:20 test_f",
        "=== [3RDPARTY] third  x1  innermost: <frozen runpy>:1 _run_code",
    ]
