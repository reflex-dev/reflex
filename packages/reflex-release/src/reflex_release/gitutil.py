"""Git and GitHub CLI helpers used by the release commands."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

from packaging.version import InvalidVersion, Version

from .actions import echo, fail, repo_url
from .config import Config, is_final

_GITHUB_REMOTE_RE = re.compile(
    r"github\.com[:/](?P<owner>[^/]+)/(?P<repo>[^/]+?)(?:\.git)?$"
)

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


def github_slug(root: Path) -> str | None:
    """Return the ``owner/repo`` slug of the origin remote, if it is on GitHub.

    Args:
        root: The repository root.

    Returns:
        The slug, or None when it cannot be determined.
    """
    result = subprocess.run(
        ["git", "remote", "get-url", "origin"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    match = _GITHUB_REMOTE_RE.search(result.stdout.strip())
    return f"{match['owner']}/{match['repo']}" if match else None


def github_repo_url(root: Path) -> str:
    """Return the web URL of the repository being released.

    Args:
        root: The repository root.

    Returns:
        The URL the workflow is running against, falling back to the origin
        remote when the command is run by hand outside GitHub Actions.
    """
    if url := repo_url():
        return url
    slug = github_slug(root)
    if slug is None:
        fail(
            "cannot determine the GitHub repository: neither GITHUB_REPOSITORY "
            "is set nor does the origin remote point at GitHub"
        )
    return f"https://github.com/{slug}"


def head_sha(root: Path) -> str:
    """Return the commit the working tree is checked out at.

    Args:
        root: The repository root.

    Returns:
        The full sha of ``HEAD``.
    """
    return git(["rev-parse", "HEAD"], root).strip()


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
    prefix = config.package_tag_prefix(package)
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


def commit_exists(root: Path, ref: str) -> bool:
    """Return whether a commit-ish resolves in the local repository.

    Args:
        root: The repository root.
        ref: The commit-ish to resolve.

    Returns:
        True when the ref names a commit that is present locally.
    """
    return bool(ref) and (
        subprocess.run(
            ["git", "rev-parse", "-q", "--verify", f"{ref}^{{commit}}"],
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
        True when origin already has the branch. A private repository needs the
        same credentials as the push that follows, since the checkout the
        workflows run on deliberately keeps none.
    """
    return (
        subprocess.run(
            [
                "git",
                *_CREDENTIAL_HELPER,
                "ls-remote",
                "--exit-code",
                "--heads",
                "origin",
                branch,
            ],
            cwd=root,
            capture_output=True,
            check=False,
        ).returncode
        == 0
    )


def gh_run(args: list[str], cwd: Path, check: bool = True) -> int:
    """Run a GitHub CLI command, letting it write straight to the job log.

    Args:
        args: The ``gh`` arguments.
        cwd: The repository directory.
        check: Whether a non-zero exit should fail the release command.

    Returns:
        The exit status of ``gh``.
    """
    echo(f"$ gh {' '.join(args)}")
    sys.stdout.flush()
    returncode = subprocess.run(["gh", *args], cwd=cwd, check=False).returncode
    if check and returncode != 0:
        fail(f"gh {' '.join(args)} failed (exit {returncode}); see the output above")
    return returncode


def gh_output(args: list[str], cwd: Path, check: bool = True) -> str:
    """Run a GitHub CLI command whose stdout is consumed by the caller.

    Args:
        args: The ``gh`` arguments.
        cwd: The repository directory.
        check: Whether a non-zero exit should fail the release command.

    Returns:
        The command's stdout, stripped. Empty when it failed and ``check`` is
        False.
    """
    result = subprocess.run(
        ["gh", *args], cwd=cwd, capture_output=True, text=True, check=False
    )
    if result.returncode != 0:
        if check:
            fail(f"gh {' '.join(args)} failed: {result.stderr.strip()}")
        return ""
    return result.stdout.strip()
