"""Run git, and merge commits without touching a working tree.

Nothing here runs code from the commits it handles: merges happen in the object
database with ``git merge-tree``, and the repository's own hooks are never invoked.
"""

from __future__ import annotations

import dataclasses
import os
import subprocess
from pathlib import Path

# The identity on commits the bot creates locally. The commit it pushes is
# recreated under the GitHub App's own identity (see on_deck.push).
IDENTITY = {
    "GIT_AUTHOR_NAME": "reflex-pr-bot",
    "GIT_AUTHOR_EMAIL": "reflex-pr-bot@users.noreply.github.com",
    "GIT_COMMITTER_NAME": "reflex-pr-bot",
    "GIT_COMMITTER_EMAIL": "reflex-pr-bot@users.noreply.github.com",
}


class GitError(RuntimeError):
    """A git command failed."""


@dataclasses.dataclass(frozen=True)
class Git:
    """A git repository on disk."""

    cwd: Path

    def run(
        self,
        *args: str,
        check: bool = True,
        env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        """Run a git command.

        Args:
            *args: The arguments after ``git``.
            check: Raise when the command fails.
            env: Variables to add to the environment.

        Returns:
            The finished process, with text output.

        Raises:
            GitError: If ``check`` is set and the command fails.
        """
        result = subprocess.run(
            ["git", *args],
            cwd=self.cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env={**os.environ, **env} if env else None,
            check=False,
        )
        if check and result.returncode != 0:
            msg = f"git {' '.join(args)} failed: {result.stderr.strip()}"
            raise GitError(msg)
        return result

    def out(self, *args: str, env: dict[str, str] | None = None) -> str:
        """Run a git command and return its output.

        Args:
            *args: The arguments after ``git``.
            env: Variables to add to the environment.

        Returns:
            Its standard output, without surrounding whitespace.
        """
        return self.run(*args, env=env).stdout.strip()

    def merge_tree(self, ours: str, theirs: str) -> tuple[str, list[str]]:
        """Merge two commits in memory.

        Args:
            ours: The first commit.
            theirs: The commit to merge into it.

        Returns:
            The merged tree (with conflict markers in conflicted files) and the
            conflicted paths, empty when the merge is clean.

        Raises:
            GitError: If git cannot merge them at all.
        """
        result = self.run(
            "merge-tree",
            "--write-tree",
            "--name-only",
            "--no-messages",
            "-z",
            ours,
            theirs,
            check=False,
        )
        if result.returncode not in (0, 1):
            msg = f"git merge-tree {ours} {theirs} failed: {result.stderr.strip()}"
            raise GitError(msg)
        tree, *conflicts = result.stdout.split("\0")
        return tree, [path for path in conflicts if path]

    def commit_tree(self, tree: str, parents: list[str], message: str) -> str:
        """Create a commit object without touching any branch.

        Args:
            tree: The commit's tree.
            parents: Its parents, in order.
            message: Its message.

        Returns:
            The new commit's id.
        """
        args = ["commit-tree", tree, "-m", message]
        for parent in parents:
            args.extend(["-p", parent])
        return self.out(*args, env=IDENTITY)

    def merged(self, base: str, head: str) -> str | None:
        """Merge a branch into its base in memory.

        Args:
            base: The base branch's commit.
            head: The pull request's head commit.

        Returns:
            A merge commit of the two, or None when they conflict.
        """
        tree, conflicts = self.merge_tree(base, head)
        if conflicts:
            return None
        return self.commit_tree(tree, [base, head], "Simulated merge")
