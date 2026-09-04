"""Fixtures for the reflex-release unit tests."""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest
from reflex_release.config import Config, load_config
from reflex_release.scaffold import CUSTOM_BUILD_CONTRACT, towncrier_config_toml

ROOT_PYPROJECT = """\
[project]
name = "mypkg"
version = "0.0.0"
dependencies = ["widget-core >= 0.1.0"]
"""

SUB_PYPROJECT = """\
[project]
name = "{name}"
version = "0.0.0"
"""


def git(repo: Path, *args: str) -> str:
    """Run a git command in a repository.

    Args:
        repo: The repository directory.
        *args: The git arguments.

    Returns:
        The command's stdout.
    """
    return subprocess.check_output(
        ["git", "-c", "user.email=t@example.com", "-c", "user.name=t", *args],
        cwd=repo,
        text=True,
    )


def commit_all(repo: Path, message: str = "wip") -> None:
    """Stage and commit everything in a repository.

    Args:
        repo: The repository directory.
        message: The commit message.
    """
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", message)


def write_lockstep(repo: Path) -> None:
    """Make the repository's two packages a lockstep group.

    The root package publishes last and pins the sub-package exactly, mirroring
    the reflex/reflex-base relationship.

    Args:
        repo: The repository root.
    """
    pyproject = repo / "pyproject.toml"
    pyproject.write_text(
        pyproject.read_text(encoding="utf-8").replace(
            "\n[tool.towncrier]",
            "\n[[tool.reflex-release.lockstep]]\n"
            'members = ["mypkg", "widget-core"]\n'
            'publish-last = ["mypkg"]\n'
            "pin-exact = true\n"
            "\n[tool.towncrier]",
        ),
        encoding="utf-8",
    )


def set_post_release_workflow(repo: Path, workflow: str) -> Config:
    """Configure a post-release workflow and reload the configuration.

    Args:
        repo: The repository root.
        workflow: The workflow to dispatch after each published tag.

    Returns:
        The reloaded configuration.
    """
    pyproject = repo / "pyproject.toml"
    pyproject.write_text(
        pyproject.read_text(encoding="utf-8").replace(
            'packages-dir = "packages"',
            f'packages-dir = "packages"\npost-release-workflow = "{workflow}"',
        ),
        encoding="utf-8",
    )
    return load_config(repo)


def write_custom_build(repo: Path, extra: str = "", workflow: bool = True) -> None:
    """Configure a custom build workflow for the root package.

    Args:
        repo: The repository root.
        extra: Additional keys for the ``custom-build`` entry.
        workflow: Whether to also create the referenced workflow file.
    """
    pyproject = repo / "pyproject.toml"
    pyproject.write_text(
        pyproject.read_text(encoding="utf-8").replace(
            "\n[tool.towncrier]",
            "\n[[tool.reflex-release.custom-build]]\n"
            'packages = ["mypkg"]\n'
            'workflow = "build_wheels.yml"\n' + extra + "\n[tool.towncrier]",
        ),
        encoding="utf-8",
    )
    if workflow:
        workflows = repo / ".github" / "workflows"
        workflows.mkdir(parents=True, exist_ok=True)
        (workflows / "build_wheels.yml").write_text(
            f"name: Build wheels\n{CUSTOM_BUILD_CONTRACT}\njobs: {{}}\n",
            encoding="utf-8",
        )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """Create a git repository with a root package and one sub-package.

    Args:
        tmp_path: The pytest temporary directory.

    Returns:
        The repository root.
    """
    (tmp_path / "src" / "mypkg").mkdir(parents=True)
    (tmp_path / "packages" / "widget-core" / "src").mkdir(parents=True)
    (tmp_path / "packages" / "widget-core" / "pyproject.toml").write_text(
        SUB_PYPROJECT.format(name="widget-core"),
        encoding="utf-8",
    )
    (tmp_path / "pyproject.toml").write_text(
        ROOT_PYPROJECT + "\n[tool.reflex-release]\n"
        'root-package = "mypkg"\n'
        'packages-dir = "packages"\n\n' + towncrier_config_toml(tmp_path),
        encoding="utf-8",
    )
    for news in (tmp_path / "news", tmp_path / "packages" / "widget-core" / "news"):
        news.mkdir()
        (news / ".gitkeep").touch()
    git(tmp_path, "init", "-q", "-b", "main")
    commit_all(tmp_path, "init")
    return tmp_path


@pytest.fixture
def config(repo: Path) -> Config:
    """Load the release configuration of the temporary repository.

    Args:
        repo: The repository root.

    Returns:
        The loaded configuration.
    """
    return load_config(repo)


@pytest.fixture
def outputs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Callable[[], dict[str, str]]:
    """Capture what the commands append to ``$GITHUB_OUTPUT``.

    Args:
        tmp_path: The pytest temporary directory.
        monkeypatch: The pytest monkeypatch fixture.

    Returns:
        A callable returning the outputs written so far.
    """
    path = tmp_path / "github_output.txt"
    path.touch()
    monkeypatch.setenv("GITHUB_OUTPUT", str(path))
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(tmp_path / "summary.md"))

    def read() -> dict[str, str]:
        return dict(
            line.split("=", 1)
            for line in path.read_text(encoding="utf-8").splitlines()
            if "=" in line
        )

    return read


@pytest.fixture
def summary(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Callable[[], str]:
    """Capture what the commands append to ``$GITHUB_STEP_SUMMARY``.

    Args:
        tmp_path: The pytest temporary directory.
        monkeypatch: The pytest monkeypatch fixture.

    Returns:
        A callable returning the job summary markdown written so far.
    """
    path = tmp_path / "summary.md"
    path.touch()
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(path))
    return lambda: path.read_text(encoding="utf-8")
