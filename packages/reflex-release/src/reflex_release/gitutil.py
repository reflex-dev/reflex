"""Git and GitHub CLI helpers used by the release commands."""

from __future__ import annotations

import subprocess
from pathlib import Path

from packaging.version import InvalidVersion, Version

from .actions import fail
from .config import Config, is_final

BOT_NAME = "github-actions[bot]"
BOT_EMAIL = "41898282+github-actions[bot]@users.noreply.github.com"

# The token is supplied through gh's credential helper so it never appears in a
# remote URL or in process argv.
_CREDENTIAL_HELPER = [
    "-c",
    "credential.helper=",
    "-c",
    "credential.helper=!gh auth git-credential",
]


def git(args: list[str], cwd: Path) -> str:
    """Run a git command and return its stdout.

    Args:
        args: The git arguments (without the leading ``git``).
        cwd: The repository directory.

    Returns:
        The command's stdout.
    """
    return subprocess.check_output(["git", *args], cwd=cwd, text=True)


def git_run(args: list[str], cwd: Path) -> None:
    """Run a git command, failing the release command if it exits non-zero.

    Args:
        args: The git arguments (without the leading ``git``).
        cwd: The repository directory.
    """
    if subprocess.run(["git", *args], cwd=cwd, check=False).returncode != 0:
        fail(f"git {' '.join(args)} failed")


def git_push(refspec: str, cwd: Path) -> None:
    """Push a refspec to ``origin`` authenticating through the gh credential helper.

    Args:
        refspec: The refspec to push (e.g. ``HEAD:refs/heads/release/x``).
        cwd: The repository directory.
    """
    git_run([*_CREDENTIAL_HELPER, "push", "origin", refspec], cwd)


def configure_bot_identity(cwd: Path) -> None:
    """Set the committer identity to github-actions[bot] for this repository.

    Args:
        cwd: The repository directory.
    """
    git_run(["config", "user.name", BOT_NAME], cwd)
    git_run(["config", "user.email", BOT_EMAIL], cwd)


def git_show(root: Path, ref: str, rel_path: str) -> str | None:
    """Return a file's content at a git ref, or None if absent there.

    Args:
        root: The repository root.
        ref: The git ref (e.g. ``origin/main``).
        rel_path: Repo-relative file path.

    Returns:
        The file content at the ref, or None when the path does not exist.
    """
    result = subprocess.run(
        ["git", "show", f"{ref}:{rel_path}"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout if result.returncode == 0 else None


def changed_files(root: Path, base_ref: str) -> list[str]:
    """List the repo-relative paths changed since the merge base with a ref.

    Args:
        root: The repository root.
        base_ref: The ref to compare against (e.g. ``origin/main``).

    Returns:
        The changed paths, POSIX-style.
    """
    return [
        line
        for line in git(
            ["diff", "--name-only", f"{base_ref}...HEAD"], root
        ).splitlines()
        if line
    ]


def tag_versions(config: Config, package: str) -> list[Version]:
    """Return every PEP 440 version tagged for a package.

    Args:
        config: The repository configuration.
        package: The package name.

    Returns:
        The parsed versions, unordered.
    """
    prefix = config.tag_prefix(package)
    versions: list[Version] = []
    for line in git(["tag", "-l", f"{prefix}*"], cwd=config.root).splitlines():
        raw = line.removeprefix(prefix).strip()
        if not raw:
            continue
        try:
            versions.append(Version(raw))
        except InvalidVersion:
            continue
    return versions


def latest_tag_version(config: Config, package: str) -> Version | None:
    """Return the largest PEP 440 version tagged for a package.

    Args:
        config: The repository configuration.
        package: The package name.

    Returns:
        The largest tagged version, or None if the package has no tags.
    """
    versions = tag_versions(config, package)
    return max(versions) if versions else None


def latest_final_tag_version(config: Config, package: str) -> Version | None:
    """Return the largest final (non-pre, non-dev) version tagged for a package.

    Args:
        config: The repository configuration.
        package: The package name.

    Returns:
        The largest final tagged version, or None if there is none.
    """
    finals = [version for version in tag_versions(config, package) if is_final(version)]
    return max(finals) if finals else None


def tag_exists(root: Path, tag: str) -> bool:
    """Return whether a git tag exists in the local repository.

    Args:
        root: The repository root.
        tag: The tag name.

    Returns:
        True when the tag exists.
    """
    return (
        subprocess.run(
            ["git", "rev-parse", "-q", "--verify", f"refs/tags/{tag}"],
            cwd=root,
            capture_output=True,
            check=False,
        ).returncode
        == 0
    )


def remote_branch_exists(root: Path, branch: str) -> bool:
    """Return whether a branch exists on ``origin``.

    Args:
        root: The repository root.
        branch: The branch name.

    Returns:
        True when origin already has the branch.
    """
    return (
        subprocess.run(
            ["git", "ls-remote", "--exit-code", "--heads", "origin", branch],
            cwd=root,
            capture_output=True,
            check=False,
        ).returncode
        == 0
    )


def gh(
    args: list[str], cwd: Path, check: bool = True
) -> subprocess.CompletedProcess[str]:
    """Run a GitHub CLI command.

    Args:
        args: The ``gh`` arguments.
        cwd: The repository directory.
        check: Whether a non-zero exit should fail the release command.

    Returns:
        The completed process, with stdout and stderr captured.
    """
    result = subprocess.run(
        ["gh", *args], cwd=cwd, capture_output=True, text=True, check=False
    )
    if check and result.returncode != 0:
        fail(f"gh {' '.join(args)} failed: {result.stderr.strip()}")
    return result
