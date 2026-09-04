"""Git and GitHub CLI helpers used by the release commands."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from packaging.version import InvalidVersion, Version

from .actions import echo, fail
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


def _log_message(root: Path, args: list[str], rel_path: str) -> str | None:
    """Return the message of the first commit a path-limited ``git log`` selects.

    The path is passed as a ``:(literal)`` pathspec: a filename holding ``*``,
    ``?`` or brackets is a glob to git, which would read some other file's
    history.

    Args:
        root: The repository root.
        args: Extra ``git log`` arguments placed before the pathspec.
        rel_path: Repo-relative file path.

    Returns:
        The commit message, or None when the log selected no commit.
    """
    result = subprocess.run(
        [
            "git",
            "log",
            *args,
            "--max-count=1",
            "--format=%B",
            "--",
            f":(literal){rel_path}",
        ],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def adding_commit_messages(root: Path, rel_path: str) -> list[str]:
    """Return the messages of the commits that brought a file into ``HEAD``.

    Two candidates, most specific first, because which one carries the pull
    request number depends on the repository's merge strategy:

    1. the commit that added the path along ``HEAD``'s first-parent line, which
       is the merge commit of a non-fast-forward merge (``Merge pull request
       #N``) and the squash commit of a squash merge;
    2. the commit that created the file anywhere in history, which is that same
       squash commit, or the branch commit of a non-fast-forward merge.

    The second is what recovers the number when a fragment reaches the branch
    being released through a merge that is not a pull request — merging ``main``
    into a prerelease branch to pull new work into the train, say, where the
    first-parent commit is that plain branch merge.

    Args:
        root: The repository root.
        rel_path: Repo-relative file path.

    Returns:
        The distinct candidate messages, most specific first. Empty when the
        path is not committed in ``HEAD``: an uncommitted file is not the file
        an old commit added at the same path (a fragment an earlier release
        already consumed), so its history says nothing about it.
    """
    if (
        subprocess.run(
            ["git", "rev-parse", "-q", "--verify", f"HEAD:{rel_path}"],
            cwd=root,
            capture_output=True,
            check=False,
        ).returncode
        != 0
    ):
        return []
    messages = [
        _log_message(root, ["--first-parent", "--diff-filter=A"], rel_path),
        _log_message(root, ["--diff-filter=A"], rel_path),
    ]
    return list(dict.fromkeys(message for message in messages if message))


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


def gh_capture(args: list[str], cwd: Path) -> tuple[int, str, str]:
    """Run a GitHub CLI command, returning everything it reported.

    For callers that have to tell one failure from another: through an exit
    status alone, "GitHub says there is no such release" and "GitHub could not
    be asked" are the same answer.

    Args:
        args: The ``gh`` arguments.
        cwd: The repository directory.

    Returns:
        The exit status, and stdout and stderr, both stripped.
    """
    result = subprocess.run(
        ["gh", *args], cwd=cwd, capture_output=True, text=True, check=False
    )
    return result.returncode, result.stdout.strip(), result.stderr.strip()


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
    returncode, stdout, stderr = gh_capture(args, cwd)
    if returncode != 0:
        if check:
            fail(f"gh {' '.join(args)} failed: {stderr}")
        return ""
    return stdout
