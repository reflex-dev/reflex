"""Fakes and builders for the pull request bot's tests."""

from __future__ import annotations

import dataclasses
import json
import subprocess
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from email.message import Message
from pathlib import Path
from typing import Any

import pytest

from scripts.pr_bot.github import GitHub, GitHubError
from scripts.pr_bot.llm import Claude
from scripts.pr_bot.pulls import (
    Actor,
    Check,
    CheckState,
    Comment,
    PullRequest,
    Review,
    Thread,
)

START = datetime(2026, 9, 1, tzinfo=timezone.utc)
AUTHOR = Actor("contributor", is_bot=False)
MAINTAINER = Actor("maintainer", is_bot=False)
GREPTILE = Actor("greptile-apps", is_bot=True)


def at(hours: float) -> datetime:
    """Return a point in time relative to a fixed start.

    Args:
        hours: Hours after the start.

    Returns:
        The time.
    """
    return START + timedelta(hours=hours)


def pull_request(**changes: Any) -> PullRequest:
    """Build a pull request that is open, mergeable and waiting for review.

    Args:
        **changes: Fields to override.

    Returns:
        The pull request.
    """
    defaults = PullRequest(
        number=7,
        title="Fix the thing",
        body="Fixes #1.",
        url="https://github.com/reflex-dev/reflex/pull/7",
        author=AUTHOR,
        is_draft=False,
        base_ref="main",
        head_ref="fix-thing",
        head_sha="a" * 40,
        head_repository="contributor/reflex",
        cross_repository=True,
        maintainer_can_modify=True,
        mergeable="MERGEABLE",
        merge_state="CLEAN",
        review_decision=None,
        additions=10,
        deletions=2,
        changed_files=1,
        labels=frozenset(),
        requested_reviewers=(),
        last_push_at=at(0),
        checks=(Check("unit-tests-gate", CheckState.PASSED),),
        opinionated_reviews=(),
        reviews=(),
        threads=(),
        comments=(),
        comment_count=0,
    )
    return dataclasses.replace(defaults, **changes)


def review(
    author: Actor,
    state: str,
    hours: float,
    body: str = "",
    association: str = "MEMBER",
    node_id: str | None = None,
) -> Review:
    """Build a submitted review.

    Args:
        author: Who reviewed.
        state: APPROVED, CHANGES_REQUESTED or COMMENTED.
        hours: When, relative to the start.
        body: The review's text.
        association: The reviewer's relationship to the repository.
        node_id: The review's id.

    Returns:
        The review.
    """
    return Review(
        node_id=node_id or f"R_{author.login}_{hours}",
        author=author,
        association=association,
        state=state,
        body=body,
        submitted_at=at(hours),
    )


def comment(
    author: Actor,
    hours: float,
    body: str = "Looks good.",
    association: str = "MEMBER",
    node_id: str | None = None,
    database_id: int = 1,
) -> Comment:
    """Build a conversation comment.

    Args:
        author: Who commented.
        hours: When, relative to the start.
        body: The comment's text.
        association: The commenter's relationship to the repository.
        node_id: The comment's node id.
        database_id: The comment's REST id.

    Returns:
        The comment.
    """
    return Comment(
        node_id=node_id or f"IC_{author.login}_{hours}",
        database_id=database_id,
        author=author,
        association=association,
        body=body,
        created_at=at(hours),
    )


def thread(
    last_author: Actor, hours: float, *, resolved: bool = False, outdated: bool = False
) -> Thread:
    """Build a review thread.

    Args:
        last_author: Who wrote its latest comment.
        hours: When, relative to the start.
        resolved: Whether it is resolved.
        outdated: Whether the code it is on has changed.

    Returns:
        The thread.
    """
    return Thread(
        resolved=resolved, outdated=outdated, last_author=last_author, last_at=at(hours)
    )


class FakeGitHub(GitHub):
    """A GitHub client that answers from memory instead of the network.

    Only the transport is replaced, so the client's own request building,
    pagination and error handling run as they do against GitHub.
    """

    def __init__(self):
        """Create a client with no routes."""
        super().__init__("token", "reflex-dev/reflex")
        self.requests: list[tuple[str, str, Any]] = []
        self.routes: dict[tuple[str, str], Any] = {}
        self.graphql_handler: Callable[[str, dict[str, Any]], Any] | None = None

    def route(self, method: str, path: str, response: Any) -> None:
        """Answer a request.

        Args:
            method: The HTTP method, or DIFF for a diff request.
            path: The path under the API root, without a query string.
            response: The JSON to return, a GitHubError to raise, or a callable
                taking the request's URL and body and returning either.
        """
        self.routes[method, path] = response

    def _send(
        self, method: str, url: str, body: Any, accept: str
    ) -> tuple[bytes, Message]:
        """Answer from the routes.

        Args:
            method: The HTTP method.
            url: The request URL or path.
            body: The JSON body.
            accept: The Accept header.

        Returns:
            The response body and (empty) headers.

        Raises:
            GitHubError: When a route says so, or when no route matches.
        """
        self.requests.append((method, url, body))
        if url == "graphql":
            assert self.graphql_handler is not None, "no GraphQL handler"
            data = self.graphql_handler(body["query"], body["variables"])
            return json.dumps({"data": data}).encode(), Message()
        path = url.split("?")[0]
        key = ("DIFF" if accept.endswith(".diff") else method, path)
        if key not in self.routes:
            if method != "GET":
                # Writes succeed unless a test routes them; tests assert on writes().
                return b"", Message()
            raise GitHubError(404, f"no route for {key}")
        response = self.routes[key]
        if callable(response):
            response = response(url, body)
        if isinstance(response, GitHubError):
            raise response
        if isinstance(response, str):
            return response.encode(), Message()
        return (b"" if response is None else json.dumps(response).encode()), Message()

    def writes(self) -> list[tuple[str, str, Any]]:
        """Return the requests that changed something.

        Returns:
            Every request other than GET and GraphQL queries.
        """
        return [
            request
            for request in self.requests
            if request[0] != "GET" and request[1] != "graphql"
        ]


class FakeClaude(Claude):
    """A Claude client that returns canned answers."""

    def __init__(self, *answers: Any):
        """Create the client.

        Args:
            *answers: What each call returns, in order: an answer, or an exception
                to raise.
        """
        self.model = "fake"
        self.answers = list(answers)
        self.calls: list[dict[str, Any]] = []

    def ask(self, **kwargs: Any) -> Any:
        """Record the question and return the next canned answer.

        Args:
            **kwargs: The question.

        Returns:
            The answer.

        Raises:
            Exception: When the canned answer is one.
        """
        self.calls.append(kwargs)
        answer = self.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer


def git(repo: Path, *args: str) -> str:
    """Run a git command with a fixed identity.

    Args:
        repo: The repository directory.
        *args: The git arguments.

    Returns:
        The command's output, stripped.
    """
    return subprocess.run(
        [
            "git",
            "-c",
            "user.email=test@example.com",
            "-c",
            "user.name=test",
            "-c",
            "init.defaultBranch=main",
            *args,
        ],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


@dataclasses.dataclass
class Upstream:
    """A repository standing in for GitHub: branches plus refs/pull/N/head refs."""

    path: Path

    def commit(
        self, parent: str, files: dict[str, str | None], message: str = "change"
    ) -> str:
        """Commit file changes on top of a commit, without moving any branch.

        Args:
            parent: The commit to build on.
            files: Paths to new contents; None deletes the file.
            message: The commit message.

        Returns:
            The new commit.
        """
        git(self.path, "checkout", "-q", "--detach", parent)
        for name, content in files.items():
            file = self.path / name
            if content is None:
                file.unlink()
            else:
                file.parent.mkdir(parents=True, exist_ok=True)
                file.write_text(content, encoding="utf-8")
        git(self.path, "add", "-A")
        git(self.path, "commit", "-q", "-m", message)
        return git(self.path, "rev-parse", "HEAD")

    def set_ref(self, ref: str, commit: str) -> None:
        """Point a ref at a commit.

        Args:
            ref: The full ref name.
            commit: The commit.
        """
        git(self.path, "update-ref", ref, commit)

    def open_pull(self, number: int, commit: str) -> None:
        """Publish a pull request's head the way GitHub does.

        Args:
            number: The pull request number.
            commit: Its head commit.
        """
        self.set_ref(f"refs/pull/{number}/head", commit)

    def clone(self, destination: Path) -> Path:
        """Clone the repository with full history, as the workflows check it out.

        Args:
            destination: Where to clone to.

        Returns:
            The clone's path.
        """
        git(destination.parent, "clone", "-q", str(self.path), str(destination))
        return destination


@pytest.fixture
def upstream(tmp_path: Path) -> tuple[Upstream, str]:
    """Create an upstream repository with one commit on main.

    Args:
        tmp_path: The test's temporary directory.

    Returns:
        The repository and its first commit.
    """
    path = tmp_path / "upstream"
    path.mkdir()
    git(path, "init", "-q")
    lines = "".join(f"line {n}\n" for n in range(1, 21))
    (path / "app.py").write_text(lines, encoding="utf-8")
    (path / "README.md").write_text("Readme\n", encoding="utf-8")
    git(path, "add", "-A")
    git(path, "commit", "-q", "-m", "initial")
    return Upstream(path), git(path, "rev-parse", "HEAD")
