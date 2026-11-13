"""The reflex installation under test and the context passed to every hook.

The harness never imports the reflex under test: it only reads its package
metadata. Benchmarks reach reflex through subprocesses run with
:attr:`Subject.python` and :attr:`Context.env`.
"""

from __future__ import annotations

import logging
import os
import platform
import random
import subprocess
import sys
from dataclasses import dataclass, field
from importlib import metadata
from pathlib import Path
from typing import Any

from reflex_bench.schema import FixtureDoc, SubjectDoc

BASE_ENV = {
    "REFLEX_TELEMETRY_ENABLED": "false",
    "REFLEX_CHECK_LATEST_VERSION": "false",
    "NO_COLOR": "1",
    "PYTHONUNBUFFERED": "1",
    "PYTHONHASHSEED": "0",
    "REFLEX_USE_GRANIAN": "true",
}


def subject_env(python: Path) -> dict[str, str]:
    """Build the environment for subprocesses of the subject with interpreter ``python``.

    Commands the subject starts by name (reflex 0.8.x starts ``granian`` in
    production mode) come from its environment, not the harness's.

    Args:
        python: The subject's interpreter.

    Returns:
        A copy of ``os.environ`` with telemetry, update checks and colors off,
        unbuffered output, a fixed hash seed, granian as the backend server and
        the directory of ``python`` first on ``PATH``.
    """
    env = {**os.environ, **BASE_ENV}
    env["PATH"] = os.pathsep.join(filter(None, (str(python.parent), env.get("PATH"))))
    return env


def git(cwd: Path, *args: str) -> str | None:
    """Run a git command.

    Args:
        cwd: The directory to run it in.
        *args: The git arguments.

    Returns:
        The stripped stdout, or ``None`` when git is missing or the command fails.
    """
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return proc.stdout.strip() if proc.returncode == 0 else None


def git_root(start: Path) -> Path | None:
    """Find the root of the git checkout containing a directory.

    Args:
        start: A directory inside the checkout.

    Returns:
        The checkout root, or ``None`` outside a checkout.
    """
    root = git(start, "rev-parse", "--show-toplevel")
    return Path(root) if root else None


def git_state(root: Path) -> tuple[str | None, bool | None]:
    """Read the commit and dirtiness of a checkout.

    Untracked files do not make a checkout dirty (``git describe --dirty``).

    Args:
        root: The checkout root.

    Returns:
        ``(commit sha, dirty)``, each ``None`` when unknown.
    """
    commit = git(root, "rev-parse", "HEAD")
    if commit is None:
        return None, None
    status = git(root, "status", "--porcelain", "--untracked-files=no")
    return commit, None if status is None else bool(status)


def installed_version(distribution: str) -> str | None:
    """Read an installed distribution's version from its metadata, without importing it.

    Args:
        distribution: The distribution name.

    Returns:
        The version, or ``None`` when it is not installed.
    """
    try:
        return metadata.version(distribution)
    except metadata.PackageNotFoundError:
        return None


@dataclass
class Subject:
    """The reflex installation under test.

    Attributes:
        spec: How the subject was requested, e.g. ``workspace``.
        source: Where it comes from: workspace, pypi, git or path.
        python: The interpreter of the subject's environment.
        reflex_version: The installed reflex version.
        commit: The git commit of the source, when known.
        dirty: Whether the source had uncommitted changes, when known.
        python_version: The interpreter's version.
        extra: Further tool versions (bun, node, ...).
    """

    spec: str
    source: str
    python: Path
    reflex_version: str | None
    commit: str | None
    dirty: bool | None
    python_version: str
    extra: dict[str, str] = field(default_factory=dict)

    @property
    def identity(self) -> str:
        """Identify the code under test, e.g. to key ``setup_cache`` results.

        Returns:
            The commit with a ``-dirty`` suffix for uncommitted changes, or the
            spec when the commit is unknown.
        """
        if self.commit is None:
            return self.spec
        return f"{self.commit}-dirty" if self.dirty else self.commit

    def to_doc(self) -> SubjectDoc:
        """Describe the subject for the result document.

        Returns:
            The subject entry.
        """
        return {
            "spec": self.spec,
            "source": self.source,
            "python": str(self.python),
            "python_version": self.python_version,
            "reflex_version": self.reflex_version,
            "commit": self.commit,
            "dirty": self.dirty,
            "extra": dict(self.extra),
        }


def workspace_subject(cwd: Path | None = None) -> Subject:
    """Describe the reflex installed in the harness's own environment (the current checkout).

    Args:
        cwd: A directory inside the checkout; defaults to the working directory.

    Returns:
        The ``workspace`` subject.
    """
    root = git_root(cwd or Path.cwd())
    commit, dirty = git_state(root) if root else (None, None)
    return Subject(
        spec="workspace",
        source="workspace",
        python=Path(sys.executable),
        reflex_version=installed_version("reflex"),
        commit=commit,
        dirty=dirty,
        python_version=platform.python_version(),
    )


@dataclass
class Context:
    """What every hook receives.

    Attributes:
        subject: The reflex installation under test.
        params: The instance's parameters, hidden ones included.
        workdir: A fresh temporary directory for this instance, removed after
            ``cleanup`` unless the run keeps it.
        cache_dir: A persistent directory per subject identity, benchmark id and
            parameter set for ``setup_cache`` results; it survives across
            invocations, so hooks decide what to reuse.
        subject_cache_dir: A persistent directory per subject identity, shared
            by all its benchmarks, for what every instance would otherwise
            prime again (a bun download).
        env: The environment for subprocesses (see :func:`subject_env`).
        rng: A seeded random generator.
        log: A logger for the benchmark.
        arm: The arm being measured, ``A`` or ``B``.
        dims: What a hook records to tell this instance's series from others
            with the same id and parameters, e.g. ``{"memory_method": "cgroup"}``;
            copied into the entry's ``dims`` after ``setup``. It must not depend
            on the arm.
        fixture: The app the benchmark drives; set in ``setup_cache`` or
            ``setup``, its name is recorded in the entry's ``dims`` and its
            content hash in the entry's ``fixture_hash``.
    """

    subject: Subject
    params: dict[str, Any]
    workdir: Path
    cache_dir: Path
    subject_cache_dir: Path
    env: dict[str, str]
    rng: random.Random
    log: logging.Logger
    arm: str = "A"
    dims: dict[str, Any] = field(default_factory=dict)
    fixture: FixtureDoc | None = None
