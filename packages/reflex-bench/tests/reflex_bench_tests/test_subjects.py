"""Tests for reflex_bench.subjects."""

from __future__ import annotations

import dataclasses
import json
import os
import platform
import re
import subprocess
import sys
import threading
import time
from collections.abc import Callable, Sequence
from datetime import timedelta
from pathlib import Path

import pytest
from reflex_bench import subjects
from reflex_bench.context import Subject, installed_version

ELLIPSIS = "\N{HORIZONTAL ELLIPSIS}"


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-c", "user.email=t@example.com", "-c", "user.name=t", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _worktrees(repo: Path) -> list[Path]:
    listing = _git(repo, "worktree", "list", "--porcelain")
    return [
        Path(line.removeprefix("worktree ")).resolve()
        for line in listing.splitlines()
        if line.startswith("worktree ")
    ]


def _checkout(path: Path, *, lock: bool = True, git: bool = True) -> Path:
    """Create a minimal reflex checkout.

    Args:
        path: Where to create it.
        lock: Whether it has a uv.lock.
        git: Whether it is a git repository with one commit, tagged v0.0.1.

    Returns:
        The checkout.
    """
    path.mkdir(parents=True, exist_ok=True)
    (path / "pyproject.toml").write_text(
        '[project]\nname = "reflex"\nversion = "0.0.1"\n', encoding="utf-8"
    )
    if lock:
        (path / "uv.lock").write_text("version = 1\n", encoding="utf-8")
    if git:
        _git(path, "init", "-q")
        _git(path, "add", ".")
        _git(path, "commit", "-q", "-m", "init")
        _git(path, "tag", "v0.0.1")
    return path


class FakeUv:
    """Stands in for uv and the subject interpreter behind subjects.run.

    git commands still run for real.
    """

    def __init__(self, real_run: Callable[..., str]) -> None:
        """Start with no calls.

        Args:
            real_run: Runs the git commands.
        """
        self.real_run = real_run
        self.calls: list[tuple[list[str], Path | None]] = []
        self.reflex_version: str | None = "0.8.23"
        self.fail_install: str | None = None
        self.fail_probe: str | None = None
        self.fail_move: str | None = None
        self.venv_gate: threading.Event | None = None

    def __call__(self, cmd: Sequence[str | Path], *, cwd: Path | None = None) -> str:
        """Record a command and pretend to run it.

        Args:
            cmd: The command.
            cwd: Its working directory.

        Returns:
            What the command would print.

        Raises:
            SubjectError: When the command is set to fail.
            AssertionError: On an unexpected command.
        """
        args = [str(part) for part in cmd]
        if args[:3] == ["git", "worktree", "move"] and self.fail_move is not None:
            raise subjects.SubjectError(self.fail_move)
        if args[0] == "git":
            return self.real_run(cmd, cwd=cwd)
        self.calls.append((args, cwd))
        if args[:2] == ["uv", "venv"]:
            if self.venv_gate is not None:
                assert self.venv_gate.wait(10)
            python = subjects.venv_python(Path(args[-1]))
            python.parent.mkdir(parents=True, exist_ok=True)
            python.write_text("", encoding="utf-8")
            return ""
        if args[:3] == ["uv", "pip", "install"]:
            if self.fail_install is not None:
                raise subjects.SubjectError(self.fail_install)
            return ""
        if args[:2] == ["uv", "export"]:
            return "-e .\nrich==14.0.0\n"
        if args[1] == "-c":
            if self.fail_probe is not None:
                raise subjects.SubjectError(self.fail_probe)
            return json.dumps({
                "python": "3.12.8",
                "reflex": self.reflex_version,
                "granian": "2.6.0",
            })
        msg = f"unexpected command {args}"
        raise AssertionError(msg)

    def count(self, *prefix: str) -> int:
        """Count the recorded commands that start with ``prefix``.

        Args:
            *prefix: The first arguments.

        Returns:
            The count.
        """
        return sum(args[: len(prefix)] == list(prefix) for args, _ in self.calls)

    def first(self, *prefix: str) -> tuple[list[str], Path | None]:
        """Find the first recorded command that starts with ``prefix``.

        Args:
            *prefix: The first arguments.

        Returns:
            The command and its working directory.
        """
        return next(
            call for call in self.calls if call[0][: len(prefix)] == list(prefix)
        )


@pytest.fixture
def uv(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> FakeUv:
    monkeypatch.setenv("UV", "uv")
    # Temporary directories must not look like part of an enclosing repository.
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))
    fake = FakeUv(subjects.run)
    monkeypatch.setattr(subjects, "run", fake)
    return fake


def _resolve(
    spec: str, home: Path, messages: list[str] | None = None, python: str = "3.12"
) -> Subject:
    echo = (messages if messages is not None else []).append
    return subjects.resolve(spec, python=python, home=home, echo=echo)


def _venv(subject: Subject) -> Path:
    return subject.python.parent.parent


@pytest.mark.parametrize(
    ("text", "source", "value", "canonical"),
    [
        ("workspace", "workspace", "", "workspace"),
        ("0.8.23", "pypi", "0.8.23", "0.8.23"),
        ("0.9.12a2", "pypi", "0.9.12a2", "0.9.12a2"),
        ("v0.9.12", "pypi", "0.9.12", "0.9.12"),
        ("git:main", "git", "main", "git:main"),
        ("git:v0.9.11", "git", "v0.9.11", "git:v0.9.11"),
        ("path:../reflex-wt-other", "path", "../reflex-wt-other", None),
    ],
)
def test_parse_spec(text: str, source: str, value: str, canonical: str | None):
    spec = subjects.parse_spec(text)
    assert (spec.source, spec.value) == (source, value)
    assert str(spec) == (canonical or text)


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("", "expected workspace, a version such as 0.8.23, git:<ref> or path:<dir>"),
        ("latest", "expected workspace, a version such as 0.8.23"),
        ("0.8.23x", "expected workspace, a version such as 0.8.23"),
        ("git:", "git: needs a commit, branch or tag"),
        ("git:-x", "a git ref may not start with '-'"),
        ("path:", "path: needs a directory"),
    ],
)
def test_parse_spec_rejects_invalid_specs(text: str, message: str):
    with pytest.raises(ValueError, match=re.escape(message)):
        subjects.parse_spec(text)


def test_cache_key(monkeypatch: pytest.MonkeyPatch):
    pypi = {"source": "pypi", "version": "0.8.23"}
    key = subjects.cache_key(pypi, "3.12")
    assert re.fullmatch(r"[0-9a-f]{16}", key)
    assert key == subjects.cache_key(dict(pypi), "3.12")
    path = {"source": "path", "path": "/src/reflex", "commit": "a" * 40, "dirty": False}
    variants = [
        ({"source": "pypi", "version": "0.8.24"}, "3.12"),
        (pypi, "3.11"),
        ({"source": "git", "commit": "a" * 40}, "3.12"),
        ({"source": "git", "commit": "b" * 40}, "3.12"),
        (path, "3.12"),
        ({**path, "dirty": True}, "3.12"),
        ({**path, "commit": "b" * 40}, "3.12"),
    ]
    keys = {key, *(subjects.cache_key(identity, py) for identity, py in variants)}
    assert len(keys) == len(variants) + 1
    monkeypatch.setattr(subjects, "SUBJECT_REQUIREMENTS", ("extra-tool",))
    assert subjects.cache_key(pypi, "3.12") != key


def test_workspace_subject_uses_the_harness_environment(
    tmp_path: Path, uv: FakeUv, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.chdir(tmp_path)
    subject = _resolve("workspace", tmp_path / "home")
    assert (subject.spec, subject.source) == ("workspace", "workspace")
    assert subject.python == Path(sys.executable)
    assert subject.reflex_version == installed_version("reflex")
    assert subject.extra == {"granian": installed_version("granian")}
    assert uv.calls == []
    assert not (tmp_path / "home").exists()


def test_pypi_subject_is_built_once_then_reused(tmp_path: Path, uv: FakeUv):
    home = tmp_path / "home"
    messages: list[str] = []
    subject = _resolve("v0.8.23", home, messages)
    venv = _venv(subject)
    assert venv.parent == home / "venvs"
    assert subject.python == subjects.venv_python(venv)
    assert subject.spec == "0.8.23"
    assert subject.source == "pypi"
    assert subject.reflex_version == "0.8.23"
    assert subject.python_version == "3.12.8"
    assert (subject.commit, subject.dirty) == (None, None)
    assert subject.extra == {"granian": "2.6.0"}
    assert messages[0] == f"building venv for reflex 0.8.23 (py3.12){ELLIPSIS}"
    assert uv.first("uv", "venv")[0][2:5] == ["--relocatable", "--python", "3.12"]
    assert uv.first("uv", "pip", "install")[0][-1] == "reflex==0.8.23"
    # Nothing is left of the build but the venv itself.
    assert [path.name for path in (home / "venvs").iterdir()] == [venv.name]

    manifest = venv / subjects.MANIFEST
    os.utime(manifest, (1_000_000, 1_000_000))
    messages.clear()
    assert _resolve("0.8.23", home, messages) == subject
    assert uv.count("uv") == 2
    assert messages == [f"reusing venv {venv.name} for reflex 0.8.23 (py3.12)"]
    # Reuse counts as use.
    assert manifest.stat().st_mtime > 1_000_000


def test_other_pythons_get_their_own_venv(tmp_path: Path, uv: FakeUv):
    first = _resolve("0.8.23", tmp_path)
    second = _resolve("0.8.23", tmp_path, python="3.11")
    assert _venv(first) != _venv(second)
    assert uv.count("uv", "venv") == 2


def test_a_failed_build_leaves_nothing_behind(tmp_path: Path, uv: FakeUv):
    uv.fail_install = "no reflex 9.9.9 on PyPI"
    with pytest.raises(
        subjects.SubjectError, match=re.escape("no reflex 9.9.9 on PyPI")
    ):
        _resolve("9.9.9", tmp_path)
    assert list((tmp_path / "venvs").iterdir()) == []
    uv.fail_install = None
    assert _venv(_resolve("9.9.9", tmp_path)).is_dir()


def test_a_half_built_venv_is_never_reused(tmp_path: Path, uv: FakeUv):
    subject = _resolve("0.8.23", tmp_path)
    venv = _venv(subject)
    # A build interrupted before its rename leaves a temporary directory behind.
    leftover = venv.with_name(f".tmp-{venv.name}-crashed")
    venv.rename(leftover)
    assert _resolve("0.8.23", tmp_path) == subject
    assert uv.count("uv", "venv") == 2
    assert leftover.is_dir()
    # A directory without a manifest was not built by reflex-bench: replace it.
    (venv / subjects.MANIFEST).unlink()
    assert _resolve("0.8.23", tmp_path) == subject
    assert uv.count("uv", "venv") == 3
    assert (venv / subjects.MANIFEST).is_file()


def test_a_broken_venv_is_rebuilt(tmp_path: Path, uv: FakeUv):
    venv = _venv(_resolve("0.8.23", tmp_path))
    uv.reflex_version = None
    messages: list[str] = []
    with pytest.raises(subjects.SubjectError, match="reflex is not installed"):
        _resolve("0.8.23", tmp_path, messages)
    assert messages[0] == (
        f"venv {venv.name} is broken (reflex is not installed): rebuilding it"
    )
    assert uv.count("uv", "venv") == 2


def test_a_venv_whose_interpreter_fails_is_rebuilt(tmp_path: Path, uv: FakeUv):
    venv = _venv(_resolve("0.8.23", tmp_path))
    uv.fail_probe = "cannot run python: gone\nmore detail"
    messages: list[str] = []
    with pytest.raises(subjects.SubjectError, match="cannot run python: gone"):
        _resolve("0.8.23", tmp_path, messages)
    assert messages[0] == (
        f"venv {venv.name} is broken (cannot run python: gone): rebuilding it"
    )
    # The failed rebuild left the old venv in place.
    assert (venv / subjects.MANIFEST).is_file()


def test_resolve_rejects_invalid_specs(tmp_path: Path):
    with pytest.raises(subjects.SubjectError, match="expected workspace, a version"):
        _resolve("latest", tmp_path)


def test_probe_rejects_nonsense(monkeypatch: pytest.MonkeyPatch):
    for output in ("Traceback (most recent call last):\nnot json", ""):
        monkeypatch.setattr(subjects, "run", lambda cmd, cwd=None, out=output: out)
        with pytest.raises(subjects.SubjectError, match="unexpected answer from"):
            subjects.probe(Path(sys.executable))


def test_concurrent_resolves_build_once(tmp_path: Path, uv: FakeUv):
    uv.venv_gate = threading.Event()
    waiting = threading.Event()
    messages: list[str] = []
    results: dict[str, Subject] = {}

    def second_echo(message: str) -> None:
        messages.append(message)
        if message.startswith("waiting for"):
            waiting.set()

    def resolve(name: str, echo: Callable[[str], None]) -> None:
        results[name] = subjects.resolve(
            "0.8.23", python="3.12", home=tmp_path, echo=echo
        )

    first = threading.Thread(target=resolve, args=("first", lambda _: None))
    first.start()
    deadline = time.monotonic() + 10
    while not uv.count("uv", "venv") and time.monotonic() < deadline:
        time.sleep(0.01)
    second = threading.Thread(target=resolve, args=("second", second_echo))
    second.start()
    assert waiting.wait(10)
    uv.venv_gate.set()
    first.join(10)
    second.join(10)
    assert results["first"] == results["second"]
    assert uv.count("uv", "venv") == 1
    assert messages[-1].startswith("reusing venv")


def test_git_subject_is_installed_from_a_snapshot(
    tmp_path: Path, uv: FakeUv, monkeypatch: pytest.MonkeyPatch
):
    repo = _checkout(tmp_path / "repo")
    commit = _git(repo, "rev-parse", "HEAD")
    monkeypatch.chdir(repo)
    home = tmp_path / "home"
    uv.reflex_version = "0.0.1"
    messages: list[str] = []
    subject = _resolve("git:v0.0.1", home, messages)
    snapshot = home / "src" / commit
    assert (subject.spec, subject.source) == ("git:v0.0.1", "git")
    assert (subject.commit, subject.dirty) == (commit, False)
    assert subject.reflex_version == "0.0.1"
    assert _git(snapshot, "rev-parse", "HEAD") == commit
    assert f"building venv for git:v0.0.1 ({commit[:12]}, py3.12){ELLIPSIS}" in (
        messages
    )
    assert uv.first("uv", "export")[0][2:] == [
        "--frozen",
        "--no-dev",
        "--no-hashes",
        "--package",
        "reflex",
        "--directory",
        str(snapshot),
    ]
    install, cwd = uv.first("uv", "pip", "install")
    # The exported requirements hold paths relative to the checkout.
    assert cwd == snapshot
    assert Path(install[install.index("-r") + 1]).name == subjects.REQUIREMENTS
    assert (_venv(subject) / subjects.REQUIREMENTS).read_text(encoding="utf-8") == (
        "-e .\nrich==14.0.0\n"
    )
    # Another ref of the same commit reuses the snapshot and the venv.
    assert _resolve("git:HEAD", home) == dataclasses.replace(subject, spec="git:HEAD")
    assert uv.count("uv", "venv") == 1
    assert _worktrees(repo) == [repo.resolve(), snapshot.resolve()]


def test_a_failed_checkout_leaves_nothing_behind(
    tmp_path: Path, uv: FakeUv, monkeypatch: pytest.MonkeyPatch
):
    repo = _checkout(tmp_path / "repo")
    monkeypatch.chdir(repo)
    home = tmp_path / "home"
    uv.fail_move = "git worktree move failed"
    with pytest.raises(subjects.SubjectError, match="git worktree move failed"):
        _resolve("git:v0.0.1", home)
    assert list((home / "src").iterdir()) == []
    assert _worktrees(repo) == [repo.resolve()]
    assert uv.calls == []
    uv.fail_move = None
    assert _resolve("git:v0.0.1", home).commit == _git(repo, "rev-parse", "HEAD")


def test_git_subject_errors(
    tmp_path: Path, uv: FakeUv, monkeypatch: pytest.MonkeyPatch
):
    repo = _checkout(tmp_path / "repo")
    monkeypatch.chdir(repo)
    with pytest.raises(subjects.SubjectError, match="git:nope: no commit named 'nope'"):
        _resolve("git:nope", tmp_path / "home")
    outside = tmp_path / "outside"
    outside.mkdir()
    monkeypatch.chdir(outside)
    with pytest.raises(subjects.SubjectError, match="git:main needs a git checkout"):
        _resolve("git:main", tmp_path / "home")
    assert uv.calls == []


def test_dirty_path_subjects_are_never_reused(tmp_path: Path, uv: FakeUv):
    repo = _checkout(tmp_path / "repo")
    commit = _git(repo, "rev-parse", "HEAD")
    home = tmp_path / "home"
    spec = f"path:{repo}"
    clean = _resolve(spec, home)
    assert (clean.spec, clean.source) == (f"path:{repo.resolve()}", "path")
    assert (clean.commit, clean.dirty) == (commit, False)
    assert _resolve(spec, home) == clean
    assert uv.count("uv", "venv") == 1
    assert uv.first("uv", "pip", "install")[1] == repo.resolve()

    (repo / "pyproject.toml").write_text("# changed\n", encoding="utf-8")
    for builds in (2, 3):
        messages: list[str] = []
        dirty = _resolve(spec, home, messages)
        assert dirty.dirty is True
        assert _venv(dirty) != _venv(clean)
        assert uv.count("uv", "venv") == builds
        assert messages[0] == (
            f"building venv for path:{repo.resolve()} ({commit[:12]}, dirty, py3.12):"
            f" uncommitted changes, so it is never reused{ELLIPSIS}"
        )


def test_path_subjects_outside_git_are_never_reused(tmp_path: Path, uv: FakeUv):
    checkout = _checkout(tmp_path / "plain", lock=False, git=False)
    messages: list[str] = []
    subject = _resolve(f"path:{checkout}", tmp_path / "home", messages)
    assert (subject.commit, subject.dirty) == (None, None)
    assert messages[0].endswith(f"not a git checkout, so it is never reused{ELLIPSIS}")
    # Without a uv.lock the checkout itself is installed, editable.
    assert uv.first("uv", "pip", "install")[0][-2:] == ["-e", str(checkout.resolve())]
    _resolve(f"path:{checkout}", tmp_path / "home")
    assert uv.count("uv", "venv") == 2


def test_path_subject_errors(tmp_path: Path, uv: FakeUv):
    with pytest.raises(subjects.SubjectError, match="no such directory"):
        _resolve(f"path:{tmp_path / 'missing'}", tmp_path / "home")
    with pytest.raises(subjects.SubjectError, match=re.escape("no pyproject.toml")):
        _resolve(f"path:{tmp_path}", tmp_path / "home")
    assert uv.calls == []


def test_missing_uv_is_explained(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("UV", raising=False)
    monkeypatch.setattr(subjects.shutil, "which", lambda name: None)
    with pytest.raises(subjects.SubjectError, match="needs uv"):
        _resolve("0.8.23", tmp_path)


def test_run_reports_the_output_of_failing_commands(tmp_path: Path):
    code = "import sys; print('some output'); sys.exit('went wrong')"
    with pytest.raises(subjects.SubjectError) as excinfo:
        subjects.run([sys.executable, "-c", code], cwd=tmp_path)
    assert "exited with 1" in str(excinfo.value)
    assert str(excinfo.value).endswith("went wrong")
    with pytest.raises(subjects.SubjectError, match="cannot run"):
        subjects.run([tmp_path / "missing-tool"])


def test_probe_reads_metadata_in_a_subprocess():
    assert subjects.probe(Path(sys.executable)) == subjects.Probe(
        platform.python_version(),
        installed_version("reflex"),
        installed_version("granian"),
    )


@pytest.mark.skipif(
    sys.platform == "win32", reason="the fake interpreter is a POSIX shell script"
)
def test_probe_runs_the_subject_interpreter(tmp_path: Path):
    python = tmp_path / "python"
    python.write_text(
        "#!/bin/sh\n"
        "echo 'a warning on stdout'\n"
        'echo \'{"python": "3.11.9", "reflex": "0.8.23", "granian": null}\'\n',
        encoding="utf-8",
    )
    python.chmod(0o755)
    assert subjects.probe(python) == subjects.Probe("3.11.9", "0.8.23", None)


def test_list_and_prune(tmp_path: Path, uv: FakeUv):
    home = tmp_path / "home"
    old = _venv(_resolve("0.8.23", home))
    recent = _venv(_resolve("0.9.12", home))
    (old / "module.py").write_text("x" * 1000, encoding="utf-8")
    long_ago = time.time() - timedelta(days=40).total_seconds()
    os.utime(old / subjects.MANIFEST, (long_ago, long_ago))
    leftover = home / "venvs" / f".tmp-{old.name}-crashed"
    leftover.mkdir()

    listed = subjects.cached_venvs(home)
    assert [(venv.spec, venv.python, venv.path) for venv in listed] == [
        ("0.9.12", "3.12", recent),
        ("0.8.23", "3.12", old),
    ]
    assert listed[1].size() >= 1000
    assert listed[1].last_used == pytest.approx(long_ago)

    messages: list[str] = []
    removed = subjects.prune(home, timedelta(days=30), echo=messages.append)
    assert sorted(removed) == sorted([old, leftover])
    assert not old.exists()
    assert not leftover.exists()
    assert [venv.spec for venv in subjects.cached_venvs(home)] == ["0.9.12"]
    assert subjects.prune(home, timedelta(days=30), echo=messages.append) == []
    assert subjects.cached_venvs(tmp_path / "empty") == []


def test_prune_leaves_what_a_build_holds(tmp_path: Path, uv: FakeUv):
    home = tmp_path / "home"
    venv = _venv(_resolve("0.8.23", home))
    leftover = venv.with_name(f".tmp-{venv.name}-crashed")
    leftover.mkdir()
    with subjects._locked(subjects._venv_lock(home.resolve(), venv.name)) as held:
        assert held
        assert subjects.prune(home, timedelta(0), echo=lambda _: None) == []
    assert subjects.prune(home, timedelta(0), echo=lambda _: None) == [venv, leftover]


def test_prune_removes_snapshots_no_venv_uses(
    tmp_path: Path, uv: FakeUv, monkeypatch: pytest.MonkeyPatch
):
    repo = _checkout(tmp_path / "repo")
    monkeypatch.chdir(repo)
    home = tmp_path / "home"
    venv = _venv(_resolve("git:v0.0.1", home))
    snapshot = home / "src" / _git(repo, "rev-parse", "HEAD")
    assert subjects.prune(home, timedelta(days=1), echo=lambda _: None) == []
    assert snapshot.is_dir()
    assert subjects.prune(home, timedelta(0), echo=lambda _: None) == [venv, snapshot]
    assert not snapshot.exists()
    assert snapshot.resolve() not in _worktrees(repo)


@pytest.mark.skipif(
    os.environ.get("REFLEX_BENCH_NETWORK_TESTS") != "1",
    reason="downloads reflex 0.8.23 from PyPI; set REFLEX_BENCH_NETWORK_TESTS=1",
)
def test_resolve_a_release_from_pypi(tmp_path: Path):
    messages: list[str] = []
    subject = subjects.resolve(
        "0.8.23", python="3.12", home=tmp_path, echo=messages.append
    )
    assert subject.reflex_version == "0.8.23"
    assert subject.python_version.startswith("3.12.")
    assert subject.extra["granian"]
    again = subjects.resolve(
        "0.8.23", python="3.12", home=tmp_path, echo=messages.append
    )
    assert again == subject
    assert messages[-1].startswith("reusing venv")
