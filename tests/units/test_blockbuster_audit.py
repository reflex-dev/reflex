"""Unit tests for scripts/blockbuster_audit.py (the event-loop blocking audit)."""

import os
from collections import defaultdict
from pathlib import Path

import pytest

from scripts import blockbuster_audit


@pytest.mark.parametrize("root_db", ["file", "symlink"])
def test_isolate_db_keeps_existing_databases(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, root_db: str
):
    """The audit gets a fresh database; reflex.db files in the cwd and root survive.

    Args:
        tmp_path: A temporary directory.
        monkeypatch: The pytest monkeypatch fixture.
        root_db: Whether the root's reflex.db is a file or a symlink to one.
    """
    cwd, root = tmp_path / "cwd", tmp_path / "root"
    cwd.mkdir()
    root.mkdir()
    monkeypatch.chdir(cwd)
    (cwd / "reflex.db").write_text("cwd data")
    target = tmp_path / "target.db"
    target.write_text("target data")
    if root_db == "file":
        (root / "reflex.db").write_text("root data")
    else:
        try:
            (root / "reflex.db").symlink_to(target)
        except OSError:
            pytest.skip("symlinks are not supported here")
    for name in ("REFLEX_DB_URL", "REFLEX_ASYNC_DB_URL"):
        # setenv first so monkeypatch also removes the value the helper sets.
        monkeypatch.setenv(name, "")
        monkeypatch.delenv(name)

    db_path = blockbuster_audit._isolate_db(root)

    assert (cwd / "reflex.db").read_text() == "cwd data"
    assert target.read_text() == "target data"
    assert (root / "reflex.db").read_text() == (
        "root data" if root_db == "file" else "target data"
    )
    assert db_path is not None
    assert db_path.parent.parent == root
    assert not db_path.exists()
    assert os.environ["REFLEX_DB_URL"] == f"sqlite:///{db_path.as_posix()}"
    assert (
        os.environ["REFLEX_ASYNC_DB_URL"] == f"sqlite+aiosqlite:///{db_path.as_posix()}"
    )


def test_isolate_db_leaves_explicit_urls_alone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """With both database URLs set, nothing is created, removed or changed.

    Args:
        tmp_path: A temporary directory.
        monkeypatch: The pytest monkeypatch fixture.
    """
    monkeypatch.setenv("REFLEX_DB_URL", "sqlite:///elsewhere.db")
    monkeypatch.setenv("REFLEX_ASYNC_DB_URL", "sqlite+aiosqlite:///elsewhere.db")
    (tmp_path / "reflex.db").write_text("root data")

    db_path = blockbuster_audit._isolate_db(tmp_path)

    assert (tmp_path / "reflex.db").read_text() == "root data"
    assert [path.name for path in tmp_path.iterdir()] == ["reflex.db"]
    assert db_path is None
    assert os.environ["REFLEX_DB_URL"] == "sqlite:///elsewhere.db"
    assert os.environ["REFLEX_ASYNC_DB_URL"] == "sqlite+aiosqlite:///elsewhere.db"


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
