"""The reflex under test (``--reflex SPEC``) and the virtualenvs subjects run in.

A spec is ``workspace`` (the current checkout, in the harness's own
environment), a PEP 440 version (``reflex==<version>`` from PyPI), ``git:<ref>``
(a commit of the current repository) or ``path:<dir>`` (another local
checkout). Every spec but ``workspace`` runs in its own virtualenv, never in the
harness's environment::

    <home>/venvs/<key>/        a relocatable virtualenv per subject
    <home>/src/<commit>/       a git worktree per git subject, installed from
    <home>/locks/              lock files of venvs and worktrees

The key is the first 16 hex digits of the SHA-256 of the subject's identity
(the version, the commit, or the path with its commit and dirty flag), the
``--python`` request and :data:`SUBJECT_REQUIREMENTS`. A venv is built in a
temporary directory under a lock and renamed into place when complete, so a
half-built venv is never reused and concurrent runs build it once. A path
subject with uncommitted changes, or outside git, is rebuilt every time.

A checkout with a ``uv.lock`` is installed with the dependency set of
``uv export --package reflex``, which lists every workspace package
(``reflex-base``, ``reflex-components-*``, ...) as an editable path in the
checkout: the development versions reflex pins never come from PyPI, and the
other dependencies are the locked ones. A checkout without a lock is installed
directly, editable. Versions are read by running the subject's interpreter,
never by importing reflex in the harness.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import time
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import IO, Any, Literal, NamedTuple

import click
from packaging.version import InvalidVersion, Version

from reflex_bench.context import (
    Subject,
    git,
    git_root,
    git_state,
    installed_version,
    workspace_subject,
)
from reflex_bench.store import canonical

if sys.platform == "win32":
    import msvcrt
else:
    import fcntl

Source = Literal["workspace", "pypi", "git", "path"]
Echo = Callable[[str], None]

# What a subject venv needs besides reflex and its dependencies to run
# `reflex run`; part of every cache key.
SUBJECT_REQUIREMENTS: tuple[str, ...] = ()
MANIFEST = "reflex-bench-subject.json"
REQUIREMENTS = "reflex-bench-requirements.txt"
KEY_LENGTH = 16
_COMMIT = re.compile(r"[0-9a-f]{40}(?:[0-9a-f]{24})?")
_VENV_LEFTOVER = re.compile(rf"\.tmp-[0-9a-f]{{{KEY_LENGTH}}}-.+")
_WORKTREE_LEFTOVER = re.compile(rf"\.tmp-{_COMMIT.pattern}-[0-9a-f]+")
_TAIL_LINES = 20
_SPEC_HELP = "expected workspace, a version such as 0.8.23, git:<ref> or path:<dir>"
_PROBE = """\
import importlib.metadata as metadata, json, platform
def version(name):
    try:
        return metadata.version(name)
    except metadata.PackageNotFoundError:
        return None
print(json.dumps({"python": platform.python_version(),
                  "reflex": version("reflex"), "granian": version("granian")}))
"""


class SubjectError(Exception):
    """A subject spec is invalid or its environment cannot be built."""


@dataclass(frozen=True)
class Spec:
    """A parsed subject spec.

    Attributes:
        source: Where the subject comes from.
        value: The normalized version, the git ref or the directory; empty for
            the workspace.
    """

    source: Source
    value: str

    def __str__(self) -> str:
        """Format the spec.

        Returns:
            E.g. ``workspace``, ``0.8.23``, ``git:main`` or ``path:../other``.
        """
        if self.source in ("git", "path"):
            return f"{self.source}:{self.value}"
        return self.value or self.source


def parse_spec(text: str) -> Spec:
    """Parse a ``--reflex`` value.

    Args:
        text: ``workspace``, a PEP 440 version, ``git:<ref>`` or ``path:<dir>``.

    Returns:
        The spec, with versions normalized (``v0.9.12`` is ``0.9.12``).

    Raises:
        ValueError: On anything else, saying what is expected.
    """
    if text == "workspace":
        return Spec("workspace", "")
    prefix, colon, value = text.partition(":")
    if colon and prefix == "git":
        if not value:
            msg = "git: needs a commit, branch or tag, e.g. git:main"
            raise ValueError(msg)
        if value.startswith("-"):
            msg = f"invalid {text!r}: a git ref may not start with '-'"
            raise ValueError(msg)
        return Spec("git", value)
    if colon and prefix == "path":
        if not value:
            msg = "path: needs a directory, e.g. path:../reflex-wt-other"
            raise ValueError(msg)
        return Spec("path", value)
    try:
        return Spec("pypi", str(Version(text)))
    except InvalidVersion:
        msg = f"invalid subject {text!r}: {_SPEC_HELP}"
        raise ValueError(msg) from None


def cache_key(identity: Mapping[str, Any], python: str) -> str:
    """Key the venv of a subject.

    Args:
        identity: What identifies the code under test, e.g. ``{"source": "pypi",
            "version": "0.8.23"}``.
        python: The ``--python`` request.

    Returns:
        The first 16 hex digits of the SHA-256 of the identity, the Python
        request and :data:`SUBJECT_REQUIREMENTS`.
    """
    payload = canonical({
        "identity": dict(identity),
        "python": python,
        "requirements": list(SUBJECT_REQUIREMENTS),
    })
    return hashlib.sha256(payload.encode()).hexdigest()[:KEY_LENGTH]


def venv_python(venv: Path) -> Path:
    """Locate the interpreter of a virtualenv.

    Args:
        venv: The virtualenv directory.

    Returns:
        ``Scripts/python.exe`` on Windows, ``bin/python`` elsewhere.
    """
    if sys.platform == "win32":
        return venv / "Scripts" / "python.exe"
    return venv / "bin" / "python"


def run(cmd: Sequence[str | os.PathLike[str]], *, cwd: Path | None = None) -> str:
    """Run a command to completion; every subprocess of this module runs here.

    Args:
        cmd: The command and its arguments.
        cwd: The working directory.

    Returns:
        The command's standard output.

    Raises:
        SubjectError: When the command cannot start or fails; the message ends
            with the last lines of its error output.
    """
    args = [os.fspath(part) for part in cmd]
    try:
        proc = subprocess.run(
            args,
            cwd=cwd,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except OSError as exc:
        msg = f"cannot run {args[0]}: {exc}"
        raise SubjectError(msg) from exc
    if proc.returncode:
        tail = (proc.stderr.strip() or proc.stdout.strip()).splitlines()[-_TAIL_LINES:]
        msg = f"{' '.join(args)} exited with {proc.returncode}"
        raise SubjectError("\n".join([msg + (":" if tail else ""), *tail]))
    return proc.stdout


class Probe(NamedTuple):
    """What a subject's interpreter reports about its environment."""

    python_version: str
    reflex: str | None
    granian: str | None


def probe(python: Path) -> Probe:
    """Ask an interpreter for its Python version and its reflex and granian versions.

    Only package metadata is read: reflex is not imported, by the harness or the
    interpreter.

    Args:
        python: The interpreter.

    Returns:
        The versions; a package that is not installed has ``None``.

    Raises:
        SubjectError: When the interpreter cannot run or answers nonsense.
    """
    output = run([python, "-c", _PROBE], cwd=python.parent)
    try:
        found = json.loads(output.strip().splitlines()[-1])
        return Probe(found["python"], found["reflex"], found["granian"])
    except (IndexError, KeyError, TypeError, ValueError):
        msg = f"unexpected answer from {python}: {output.strip()[-200:]!r}"
        raise SubjectError(msg) from None


class _Worktree(NamedTuple):
    """The git worktree a git subject is installed from."""

    repo: Path
    commit: str
    path: Path


@dataclass(frozen=True)
class _Build:
    """What a subject venv is built from.

    Attributes:
        spec: The spec recorded in the subject.
        label: How messages name the subject.
        identity: What the cache key hashes, besides the Python request.
        version: The PyPI version, for PyPI subjects.
        checkout: The checkout to install, for git and path subjects.
        worktree: Where a git subject's checkout comes from.
        commit: The commit of the checkout, when known.
        dirty: Whether the checkout has uncommitted changes, when known.
    """

    spec: str
    label: str
    identity: dict[str, Any]
    version: str | None = None
    checkout: Path | None = None
    worktree: _Worktree | None = None
    commit: str | None = None
    dirty: bool | None = None


def _describe(spec: Spec, home: Path) -> _Build:
    """Find out what a spec refers to.

    Args:
        spec: A PyPI, git or path spec.
        home: The bench home, where git worktrees live.

    Returns:
        What to build.

    Raises:
        SubjectError: When the ref, the repository or the directory is missing.
    """
    if spec.source == "pypi":
        return _Build(
            spec=spec.value,
            label=f"reflex {spec.value}",
            identity={"source": "pypi", "version": spec.value},
            version=spec.value,
        )
    if spec.source == "git":
        repo = git_root(Path.cwd())
        if repo is None:
            msg = f"{spec} needs a git checkout: run reflex-bench inside the reflex repository"
            raise SubjectError(msg)
        commit = git(
            repo, "rev-parse", "--verify", "--quiet", f"{spec.value}^{{commit}}"
        )
        if not commit:
            msg = f"{spec}: no commit named {spec.value!r} in {repo}"
            raise SubjectError(msg)
        worktree = _Worktree(repo, commit, home / "src" / commit)
        return _Build(
            spec=str(spec),
            label=str(spec),
            identity={"source": "git", "commit": commit},
            checkout=worktree.path,
            worktree=worktree,
            commit=commit,
            dirty=False,
        )
    checkout = Path(spec.value).expanduser().resolve()
    if not checkout.is_dir():
        msg = f"{spec}: no such directory {checkout}"
        raise SubjectError(msg)
    if not (checkout / "pyproject.toml").is_file():
        msg = f"{spec}: no pyproject.toml in {checkout}, so it is not a reflex checkout"
        raise SubjectError(msg)
    commit, dirty = git_state(checkout)
    return _Build(
        spec=f"path:{checkout}",
        label=f"path:{checkout}",
        identity={
            "source": "path",
            "path": str(checkout),
            "commit": commit,
            "dirty": dirty,
        },
        checkout=checkout,
        commit=commit,
        dirty=dirty,
    )


def _lock(handle: IO[bytes], *, wait: bool) -> bool:
    """Take an exclusive lock on an open file; closing the file releases it.

    Args:
        handle: The lock file, opened for reading and writing.
        wait: Whether to wait while another process holds the lock.

    Returns:
        Whether the lock was taken.
    """
    if sys.platform == "win32":
        handle.seek(0)
        mode = msvcrt.LK_LOCK if wait else msvcrt.LK_NBLCK
        # LK_LOCK gives up after about 10 s, so waiting means trying again.
        while True:
            with contextlib.suppress(OSError):
                msvcrt.locking(handle.fileno(), mode, 1)
                return True
            if not wait:
                return False
    try:
        fcntl.flock(handle, fcntl.LOCK_EX | (0 if wait else fcntl.LOCK_NB))
    except BlockingIOError:
        return False
    return True


@contextlib.contextmanager
def _locked(path: Path, on_wait: Callable[[], None] | None = None) -> Iterator[bool]:
    """Hold an exclusive lock file, which also works between threads.

    Args:
        path: The lock file; created when missing and never deleted, since
            deleting a lock file lets two processes hold "the" lock.
        on_wait: Called before waiting when another process holds the lock;
            without it a held lock is not waited for.

    Yields:
        Whether the lock is held.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as handle:
        held = _lock(handle, wait=False)
        if not held and on_wait is not None:
            on_wait()
            held = _lock(handle, wait=True)
        yield held


def _venv_lock(home: Path, key: str) -> Path:
    """Locate the lock file of a venv.

    Args:
        home: The bench home.
        key: The venv's cache key.

    Returns:
        The lock file.
    """
    return home / "locks" / f"venv-{key}.lock"


def _worktree_lock(home: Path, commit: str) -> Path:
    """Locate the lock file of a git worktree.

    Args:
        home: The bench home.
        commit: The worktree's commit.

    Returns:
        The lock file.
    """
    return home / "locks" / f"src-{commit}.lock"


def _uv() -> str:
    """Find the uv executable.

    Returns:
        ``$UV`` (set by ``uv run``) or ``uv`` on the PATH.

    Raises:
        SubjectError: When uv is missing.
    """
    uv = os.environ.get("UV") or shutil.which("uv")
    if not uv:
        msg = "building subject venvs needs uv (https://docs.astral.sh/uv/), which is not on the PATH"
        raise SubjectError(msg)
    return uv


def _remove(path: Path) -> None:
    """Delete a directory; a git worktree is also unregistered from its repository.

    Args:
        path: The directory.
    """
    with contextlib.suppress(SubjectError):
        run(["git", "worktree", "remove", "--force", path], cwd=path)
    shutil.rmtree(path, ignore_errors=True)


def _check_out(worktree: _Worktree, echo: Echo) -> None:
    """Check out a commit as a detached git worktree, unless it exists already.

    The worktree is created next to its place and moved there, so a half-created
    one is never reused. A worktree (unlike ``git archive``) keeps the tags that
    the dynamic versions of the workspace packages are computed from.

    Args:
        worktree: The worktree to create.
        echo: Receives progress messages.
    """
    if worktree.path.is_dir():
        return
    echo(
        f"checking out {worktree.commit[:12]} into {worktree.path}\N{HORIZONTAL ELLIPSIS}"
    )
    worktree.path.parent.mkdir(parents=True, exist_ok=True)
    tmp = worktree.path.with_name(f".tmp-{worktree.commit}-{secrets.token_hex(4)}")
    try:
        # A registered but deleted worktree would block the move.
        run(["git", "worktree", "prune"], cwd=worktree.repo)
        run(
            ["git", "worktree", "add", "--detach", tmp, worktree.commit],
            cwd=worktree.repo,
        )
        run(["git", "worktree", "move", tmp, worktree.path], cwd=worktree.repo)
    except BaseException:
        _remove(tmp)
        raise


def _reusable(venv: Path, echo: Echo) -> Probe | None:
    """Check that a built venv still works.

    Args:
        venv: The venv directory.
        echo: Told when the venv is broken.

    Returns:
        The probe of a working venv, else ``None``.
    """
    if not (venv / MANIFEST).is_file():
        return None
    try:
        found = probe(venv_python(venv))
    except SubjectError as exc:
        reason = str(exc).splitlines()[0]
    else:
        if found.reflex is not None:
            return found
        reason = "reflex is not installed"
    echo(f"venv {venv.name} is broken ({reason}): rebuilding it")
    return None


def _replace(new: Path, target: Path) -> None:
    """Move a directory into place, replacing any old one.

    Args:
        new: The complete new directory.
        target: Where it goes.
    """
    if not target.exists():
        new.rename(target)
        return
    old = target.with_name(f".tmp-{target.name}-old-{secrets.token_hex(4)}")
    target.rename(old)
    new.rename(target)
    shutil.rmtree(old, ignore_errors=True)


def _probe_reflex(python: Path, label: str) -> Probe:
    """Probe a newly built venv, which must have reflex.

    Args:
        python: The venv's interpreter.
        label: How messages name the subject.

    Returns:
        The probe.

    Raises:
        SubjectError: When reflex is not installed.
    """
    found = probe(python)
    if found.reflex is None:
        msg = f"reflex is not installed in the venv built for {label}"
        raise SubjectError(msg)
    return found


def _build(build: _Build, venv: Path, python: str, cwd: Path) -> Probe:
    """Build a subject venv in a temporary directory and rename it into place.

    Args:
        build: What to install.
        venv: Where the venv goes.
        python: The ``--python`` request.
        cwd: Where uv runs, which decides the uv configuration it reads.

    Returns:
        The probe of the new venv.

    Raises:
        SubjectError: When uv fails or reflex ends up missing.
    """
    uv = _uv()
    venv.parent.mkdir(parents=True, exist_ok=True)
    # Not mkdtemp: its 0700 mode would stay with the venv.
    tmp = venv.with_name(f".tmp-{venv.name}-{secrets.token_hex(4)}")
    tmp.mkdir()
    try:
        run([uv, "venv", "--relocatable", "--python", python, tmp], cwd=cwd)
        install = [uv, "pip", "install", "--python", venv_python(tmp)]
        install.extend(SUBJECT_REQUIREMENTS)
        if build.checkout is None:
            run([*install, f"reflex=={build.version}"], cwd=cwd)
        elif (build.checkout / "uv.lock").is_file():
            exported = run(
                [uv, "export", "--frozen", "--no-dev", "--no-hashes", "--package",
                 "reflex", "--directory", build.checkout],
                cwd=build.checkout,
            )  # fmt: skip
            requirements = tmp / REQUIREMENTS
            requirements.write_text(exported, encoding="utf-8")
            # The workspace packages are paths relative to the checkout.
            run([*install, "-r", requirements], cwd=build.checkout)
        else:
            run([*install, "-e", build.checkout], cwd=build.checkout)
        found = _probe_reflex(venv_python(tmp), build.label)
        manifest = {
            "spec": build.spec,
            "source": build.identity["source"],
            "python": python,
            "snapshot": None if build.worktree is None else str(build.worktree.path),
        }
        (tmp / MANIFEST).write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        _replace(tmp, venv)
    except BaseException:
        shutil.rmtree(tmp, ignore_errors=True)
        raise
    return found


def _stderr(message: str) -> None:
    """Print a progress message to standard error.

    Args:
        message: The message.
    """
    click.echo(message, err=True)


def resolve(spec: str, *, python: str, home: Path, echo: Echo = _stderr) -> Subject:
    """Build or reuse the environment of a subject, and describe the subject.

    Everything happens before any timing starts: builds take minutes.

    Args:
        spec: ``workspace``, a version, ``git:<ref>`` or ``path:<dir>``.
        python: The Python of the subject venv, as ``uv venv --python`` takes it
            (e.g. ``3.12``); the workspace always uses the harness's interpreter.
        home: The bench home.
        echo: Receives progress messages.

    Returns:
        The subject: its venv interpreter, reflex, Python and granian versions
        (read by running that interpreter), and the commit and dirty flag of
        git and path subjects.

    Raises:
        SubjectError: When the spec is invalid or its environment cannot be built.
    """
    try:
        parsed = parse_spec(spec)
    except ValueError as exc:
        raise SubjectError(str(exc)) from exc
    if parsed.source == "workspace":
        subject = workspace_subject()
        if granian := installed_version("granian"):
            subject.extra["granian"] = granian
        return subject
    home = home.resolve()
    build = _describe(parsed, home)
    key = cache_key(build.identity, python)
    venv = home / "venvs" / key
    details = ", ".join([
        *([build.commit[:12]] if build.commit else []),
        *(["dirty"] if build.dirty else []),
        f"py{python}",
    ])
    rebuild = ""
    if parsed.source == "path" and build.dirty is not False:
        reason = "uncommitted changes" if build.dirty else "not a git checkout"
        rebuild = f": {reason}, so it is never reused"
    with contextlib.ExitStack() as stack:
        stack.enter_context(
            _locked(
                _venv_lock(home, key),
                lambda: echo(
                    f"waiting for another reflex-bench to finish building venv {key}"
                    "\N{HORIZONTAL ELLIPSIS}"
                ),
            )
        )
        if build.worktree is not None:
            # Builds install from the worktree and may write into it (pyi stubs).
            lock = _worktree_lock(home, build.worktree.commit)
            stack.enter_context(_locked(lock, lambda: None))
            _check_out(build.worktree, echo)
        found = None if rebuild else _reusable(venv, echo)
        if found is None:
            echo(
                f"building venv for {build.label} ({details}){rebuild}\N{HORIZONTAL ELLIPSIS}"
            )
            started = time.perf_counter()
            found = _build(build, venv, python, build.checkout or home)
            echo(f"built venv {key} in {time.perf_counter() - started:.1f} s")
        else:
            echo(f"reusing venv {key} for {build.label} ({details})")
        # The manifest's modification time is when the venv was last used.
        os.utime(venv / MANIFEST)
    return Subject(
        spec=build.spec,
        source=parsed.source,
        python=venv_python(venv),
        reflex_version=found.reflex,
        commit=build.commit,
        dirty=build.dirty,
        python_version=found.python_version,
        extra={} if found.granian is None else {"granian": found.granian},
    )


@dataclass(frozen=True)
class CachedVenv:
    """A subject venv in the bench home.

    Attributes:
        key: Its cache key, the directory name.
        path: The venv directory.
        spec: The spec it was built for.
        python: The ``--python`` request it was built with.
        snapshot: The git worktree it is installed from, for git subjects.
        last_used: When a run last resolved it, in seconds since the epoch.
    """

    key: str
    path: Path
    spec: str
    python: str
    snapshot: Path | None
    last_used: float

    def size(self) -> int:
        """Add up the sizes of its files, without following symlinks.

        Returns:
            The size in bytes.
        """
        return sum(
            (Path(root) / name).lstat().st_size
            for root, _, files in os.walk(self.path)
            for name in files
        )


def cached_venvs(home: Path) -> list[CachedVenv]:
    """List the complete subject venvs of a bench home.

    Args:
        home: The bench home.

    Returns:
        The venvs, most recently used first.
    """
    venvs = home.resolve() / "venvs"
    found: list[CachedVenv] = []
    for manifest in venvs.glob(f"*/{MANIFEST}") if venvs.is_dir() else ():
        if manifest.parent.name.startswith("."):
            continue
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
            snapshot = data["snapshot"]
            found.append(
                CachedVenv(
                    key=manifest.parent.name,
                    path=manifest.parent,
                    spec=data["spec"],
                    python=data["python"],
                    snapshot=None if snapshot is None else Path(snapshot),
                    last_used=manifest.stat().st_mtime,
                )
            )
        except (OSError, ValueError, KeyError, TypeError):
            continue
    return sorted(found, key=lambda venv: venv.last_used, reverse=True)


def prune(home: Path, older_than: timedelta, *, echo: Echo = _stderr) -> list[Path]:
    """Delete venvs not used for a while and what nothing needs any more.

    Also deletes the leftovers of interrupted builds and the git worktrees no
    venv is installed from. Anything a running build holds is left alone.

    Args:
        home: The bench home.
        older_than: How long a venv must have gone unused.
        echo: Receives one message per deleted directory.

    Returns:
        The deleted directories.
    """
    home = home.resolve()
    cutoff = time.time() - older_than.total_seconds()
    removed: list[Path] = []
    for venv in cached_venvs(home):
        if venv.last_used >= cutoff:
            continue
        with _locked(_venv_lock(home, venv.key)) as held:
            manifest = venv.path / MANIFEST
            # A run may have used it since it was listed.
            if not held or not manifest.is_file() or manifest.stat().st_mtime >= cutoff:
                continue
            shutil.rmtree(venv.path, ignore_errors=True)
        echo(f"removed {venv.path} ({venv.spec}, py{venv.python})")
        removed.append(venv.path)
    # Only names this module creates are ever deleted.
    for directory, pattern, lock in (
        (home / "venvs", _VENV_LEFTOVER, _venv_lock),
        (home / "src", _WORKTREE_LEFTOVER, _worktree_lock),
    ):
        for leftover in _matching(directory, pattern):
            with _locked(lock(home, leftover.name.split("-")[1])) as held:
                if not held:
                    continue
                _remove(leftover)
            echo(f"removed {leftover} (left by an interrupted build)")
            removed.append(leftover)
    for worktree in _matching(home / "src", _COMMIT):
        with _locked(_worktree_lock(home, worktree.name)) as held:
            # Checked under the lock: a build may have started using it.
            if not held or worktree in {venv.snapshot for venv in cached_venvs(home)}:
                continue
            _remove(worktree)
        echo(f"removed {worktree} (a git worktree no venv uses)")
        removed.append(worktree)
    return removed


def _matching(directory: Path, pattern: re.Pattern[str]) -> list[Path]:
    """List the subdirectories whose names match a pattern.

    Args:
        directory: The directory; it may be missing.
        pattern: The pattern the whole name must match.

    Returns:
        The subdirectories, sorted.
    """
    if not directory.is_dir():
        return []
    return sorted(
        path
        for path in directory.iterdir()
        if pattern.fullmatch(path.name) and path.is_dir()
    )
