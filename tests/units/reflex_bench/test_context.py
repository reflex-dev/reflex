"""Tests for reflex_bench.context."""

from __future__ import annotations

import dataclasses
import subprocess
import sys
from pathlib import Path

import pytest
from reflex_bench import context


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.email=t@example.com", "-c", "user.name=t", *args],
        cwd=repo,
        check=True,
        capture_output=True,
    )


def test_base_env_overrides(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("REFLEX_TELEMETRY_ENABLED", "true")
    monkeypatch.setenv("SOMETHING_ELSE", "kept")
    env = context.base_env()
    assert env["REFLEX_TELEMETRY_ENABLED"] == "false"
    assert env["REFLEX_CHECK_LATEST_VERSION"] == "false"
    assert env["NO_COLOR"] == "1"
    assert env["PYTHONUNBUFFERED"] == "1"
    assert env["PYTHONHASHSEED"] == "0"
    assert env["REFLEX_USE_GRANIAN"] == "true"
    assert env["SOMETHING_ELSE"] == "kept"


def test_workspace_subject_reads_git_state(tmp_path: Path):
    _git(tmp_path, "init", "-q")
    (tmp_path / "file.txt").write_text("one", encoding="utf-8")
    _git(tmp_path, "add", "file.txt")
    _git(tmp_path, "commit", "-q", "-m", "init")
    subject = context.workspace_subject(tmp_path)
    assert subject.spec == subject.source == "workspace"
    assert subject.python == Path(sys.executable)
    assert subject.commit is not None
    assert len(subject.commit) == 40
    assert subject.dirty is False
    # Untracked files do not make a checkout dirty; modified tracked files do.
    (tmp_path / "untracked.txt").write_text("x", encoding="utf-8")
    assert context.workspace_subject(tmp_path).dirty is False
    (tmp_path / "file.txt").write_text("two", encoding="utf-8")
    assert context.workspace_subject(tmp_path).dirty is True


def test_workspace_subject_outside_git(tmp_path: Path):
    subject = context.workspace_subject(tmp_path)
    assert subject.commit is None
    assert subject.dirty is None
    assert subject.to_doc()["python"] == sys.executable


def test_installed_version_reads_metadata_only():
    assert context.installed_version("reflex-bench")
    assert context.installed_version("not-a-real-distribution-xyz") is None


def test_the_harness_never_imports_reflex():
    # Importing every harness module must not pull in the reflex under test.
    code = (
        "import sys, reflex_bench.cli, reflex_bench.registry;"
        "reflex_bench.registry.discover();"
        "loaded = [m for m in sys.modules if m.split('.')[0] in"
        " {'reflex', 'reflex_base'} or m.startswith('reflex_components')];"
        "assert not loaded, loaded"
    )
    subprocess.run([sys.executable, "-c", code], check=True)


def test_workspace_subject_is_a_plain_subject(tmp_path: Path):
    subject = context.workspace_subject(tmp_path)
    assert dataclasses.replace(subject, spec="git:main").spec == "git:main"


def test_subject_identity(tmp_path: Path):
    subject = context.workspace_subject(tmp_path)
    assert subject.identity == "workspace"
    clean = dataclasses.replace(subject, commit="abc", dirty=False)
    assert clean.identity == "abc"
    assert dataclasses.replace(clean, dirty=True).identity == "abc-dirty"
