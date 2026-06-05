"""Unit tests for scripts/make_pyi.py (the .pyi generation driver).

Covers the dispatch logic that decides, per invocation:
- which targets are scanned,
- whether ``pyi_hashes.json`` is pruned (full run) or merged (partial run),
- whether the ``.pyi_generator_last_run`` marker is written,

and the commit-reachability check that forces a full regeneration after a
branch switch or rebase.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import make_pyi


@pytest.fixture
def recorded_scan(monkeypatch, tmp_path: Path):
    """Replace PyiGenerator + git side effects with recording stubs.

    Args:
        monkeypatch: The pytest monkeypatch fixture.
        tmp_path: A temporary directory for the marker file.

    Returns:
        A namespace exposing ``calls`` (recorded scan_all kwargs) and ``marker``
        (the redirected last-run marker path).
    """
    calls: list[dict] = []

    class _FakeGenerator:
        def scan_all(
            self, targets, changed_files=None, use_json=False, prune_stale=False
        ):
            calls.append({
                "targets": list(targets),
                "changed_files": changed_files,
                "use_json": use_json,
                "prune_stale": prune_stale,
            })

    monkeypatch.setattr(make_pyi, "PyiGenerator", _FakeGenerator)

    marker = tmp_path / ".pyi_generator_last_run"
    monkeypatch.setattr(make_pyi, "LAST_RUN_COMMIT_SHA_FILE", marker)

    def _fake_run(cmd, *_args, **_kwargs):
        # main() only shells out for `git rev-parse HEAD` to stamp the marker.
        return subprocess.CompletedProcess(cmd, 0, stdout="deadbeefcafe\n", stderr="")

    monkeypatch.setattr(make_pyi.subprocess, "run", _fake_run)

    return SimpleNamespace(calls=calls, marker=marker)


def test_explicit_targets_merge_and_skip_marker(recorded_scan):
    """Explicit targets are merged (never pruned) and leave the marker untouched.

    Args:
        recorded_scan: The recording fixture.
    """
    make_pyi.main(["reflex/components/radix"])

    (call,) = recorded_scan.calls
    assert call["targets"] == ["reflex/components/radix"]
    assert call["changed_files"] is None
    assert call["prune_stale"] is False
    assert call["use_json"] is True
    assert not recorded_scan.marker.exists()


def test_explicit_targets_filtered_to_known_prefixes(recorded_scan):
    """Targets outside the default prefixes (e.g. tests) are dropped, no marker.

    Args:
        recorded_scan: The recording fixture.
    """
    make_pyi.main(["tests/units/test_app.py", "reflex/components/radix/foo.py"])

    (call,) = recorded_scan.calls
    assert call["targets"] == ["reflex/components/radix/foo.py"]
    assert call["prune_stale"] is False
    assert not recorded_scan.marker.exists()


def test_force_regenerates_every_default_target(recorded_scan, monkeypatch):
    """--force ignores markers, scans all default targets, prunes, stamps marker.

    Args:
        recorded_scan: The recording fixture.
        monkeypatch: The pytest monkeypatch fixture.
    """

    # _get_changed_files must NOT be consulted when --force is given.
    def _boom():
        msg = "_get_changed_files should not be called with --force"
        raise AssertionError(msg)

    monkeypatch.setattr(make_pyi, "_get_changed_files", _boom)

    make_pyi.main(["--force"])

    (call,) = recorded_scan.calls
    assert call["targets"] == make_pyi.DEFAULT_TARGETS
    assert call["changed_files"] is None
    assert call["prune_stale"] is True
    assert recorded_scan.marker.read_text() == "deadbeefcafe"


def test_default_incremental_merges_and_stamps_marker(recorded_scan, monkeypatch):
    """A default incremental run scans defaults, merges, and stamps the marker.

    Args:
        recorded_scan: The recording fixture.
        monkeypatch: The pytest monkeypatch fixture.
    """
    changed = [Path("reflex/components/radix/foo.py")]
    monkeypatch.setattr(make_pyi, "_get_changed_files", lambda: changed)

    make_pyi.main([])

    (call,) = recorded_scan.calls
    assert call["targets"] == make_pyi.DEFAULT_TARGETS
    assert call["changed_files"] == changed
    assert call["prune_stale"] is False
    assert recorded_scan.marker.read_text() == "deadbeefcafe"


def test_default_full_run_prunes_and_stamps_marker(recorded_scan, monkeypatch):
    """A default run with no detectable base regenerates everything and prunes.

    Args:
        recorded_scan: The recording fixture.
        monkeypatch: The pytest monkeypatch fixture.
    """
    monkeypatch.setattr(make_pyi, "_get_changed_files", lambda: None)

    make_pyi.main([])

    (call,) = recorded_scan.calls
    assert call["targets"] == make_pyi.DEFAULT_TARGETS
    assert call["changed_files"] is None
    assert call["prune_stale"] is True
    assert recorded_scan.marker.read_text() == "deadbeefcafe"


def _git(repo: Path, *args: str) -> str:
    """Run a git command in ``repo`` and return its stdout.

    Args:
        repo: The repository working directory.
        args: The git arguments.

    Returns:
        The command's stdout, stripped.
    """
    return subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True
    ).stdout.strip()


@pytest.fixture
def diverged_repo(tmp_path: Path):
    """Build a repo whose ``feature`` tip is unreachable from ``main``.

    Args:
        tmp_path: A temporary directory.

    Returns:
        A namespace with ``path`` (repo dir), ``main_sha`` (HEAD) and
        ``orphan_sha`` (a commit not reachable from HEAD).
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "Tester")

    (repo / "a.txt").write_text("1")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "c1")
    main_sha = _git(repo, "rev-parse", "HEAD")

    # A commit on a divergent branch that we then leave; not an ancestor of main.
    _git(repo, "checkout", "-b", "feature")
    (repo / "b.txt").write_text("2")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "c2")
    orphan_sha = _git(repo, "rev-parse", "HEAD")
    _git(repo, "checkout", "main")

    return SimpleNamespace(path=repo, main_sha=main_sha, orphan_sha=orphan_sha)


def test_commit_is_reachable(diverged_repo, monkeypatch):
    """Reachability is True for ancestors of HEAD, False otherwise.

    Args:
        diverged_repo: The diverged-repo fixture.
        monkeypatch: The pytest monkeypatch fixture.
    """
    monkeypatch.chdir(diverged_repo.path)
    assert make_pyi._commit_is_reachable(diverged_repo.main_sha) is True
    assert make_pyi._commit_is_reachable(diverged_repo.orphan_sha) is False
    assert make_pyi._commit_is_reachable("0" * 40) is False


def test_unreachable_last_run_forces_full_regen(diverged_repo, monkeypatch):
    """A marker pointing at an unreachable commit yields a full regeneration.

    Args:
        diverged_repo: The diverged-repo fixture.
        monkeypatch: The pytest monkeypatch fixture.
    """
    monkeypatch.chdir(diverged_repo.path)
    marker = diverged_repo.path / ".pyi_generator_last_run"
    marker.write_text(diverged_repo.orphan_sha)
    monkeypatch.setattr(make_pyi, "LAST_RUN_COMMIT_SHA_FILE", marker)

    assert make_pyi._get_changed_files() is None


def _write_hashes(tmp_path: Path, entries: dict[str, str], sources: list[str]) -> Path:
    """Write a pyi_hashes.json plus the given .py source files under tmp_path.

    Args:
        tmp_path: The directory to populate.
        entries: The pyi_hashes.json contents (entry path -> hash).
        sources: Relative .py paths to create as existing source files.

    Returns:
        The path to the written pyi_hashes.json.
    """
    for source in sources:
        source_path = tmp_path / source
        source_path.parent.mkdir(parents=True, exist_ok=True)
        source_path.write_text("")
    hashes_file = tmp_path / "pyi_hashes.json"
    hashes_file.write_text(json.dumps(entries, indent=2, sort_keys=True) + "\n")
    return hashes_file


def test_stale_hash_entries_detects_missing_source(tmp_path, monkeypatch):
    """Entries whose .py source is missing are reported; live ones are not.

    Args:
        tmp_path: A temporary directory.
        monkeypatch: The pytest monkeypatch fixture.
    """
    hashes_file = _write_hashes(
        tmp_path,
        {"pkg/live.pyi": "a", "pkg/ghost.pyi": "b", "pkg/sub/gone.pyi": "c"},
        sources=["pkg/live.py"],
    )
    monkeypatch.setattr(make_pyi, "PYI_HASHES_FILE", hashes_file)

    assert make_pyi._stale_hash_entries() == ["pkg/ghost.pyi", "pkg/sub/gone.pyi"]


def test_stale_hash_entries_clean(tmp_path, monkeypatch):
    """No entries are reported when every .py source exists.

    Args:
        tmp_path: A temporary directory.
        monkeypatch: The pytest monkeypatch fixture.
    """
    hashes_file = _write_hashes(
        tmp_path,
        {"pkg/live.pyi": "a", "pkg/__init__.pyi": "b"},
        sources=["pkg/live.py", "pkg/__init__.py"],
    )
    monkeypatch.setattr(make_pyi, "PYI_HASHES_FILE", hashes_file)

    assert make_pyi._stale_hash_entries() == []


def test_check_flag_passes_when_clean(tmp_path, monkeypatch):
    """`--check` returns without raising when the registry is clean.

    Args:
        tmp_path: A temporary directory.
        monkeypatch: The pytest monkeypatch fixture.
    """
    hashes_file = _write_hashes(
        tmp_path, {"pkg/live.pyi": "a"}, sources=["pkg/live.py"]
    )
    monkeypatch.setattr(make_pyi, "PYI_HASHES_FILE", hashes_file)

    make_pyi.main(["--check"])


def test_check_flag_fails_on_stale(tmp_path, monkeypatch):
    """`--check` exits non-zero when an entry has no .py source.

    Args:
        tmp_path: A temporary directory.
        monkeypatch: The pytest monkeypatch fixture.
    """
    hashes_file = _write_hashes(
        tmp_path,
        {"pkg/live.pyi": "a", "pkg/ghost.pyi": "b"},
        sources=["pkg/live.py"],
    )
    monkeypatch.setattr(make_pyi, "PYI_HASHES_FILE", hashes_file)

    with pytest.raises(SystemExit) as exc_info:
        make_pyi.main(["--check"])
    assert exc_info.value.code == 1
