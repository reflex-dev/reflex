"""Fetch what the triage rules need to know about pull requests.

One GraphQL fragment carries every fact the rules read, so triaging every open pull
request takes a handful of paginated queries rather than a dozen REST calls each.
"""

from __future__ import annotations

import dataclasses
import enum
import operator
from collections.abc import Iterator
from datetime import datetime
from typing import Any

from scripts.pr_bot.github import GitHub

_CHECK_CONTEXT = """
fragment CheckContext on StatusCheckRollupContext {
  __typename
  ... on CheckRun { name status conclusion startedAt }
  ... on StatusContext { context state createdAt }
}
"""

_FACTS = (
    """
fragment Who on Actor { __typename login }

fragment ReviewFacts on PullRequestReview {
  id state body submittedAt authorAssociation author { ...Who }
}

fragment Facts on PullRequest {
  number title body url isDraft
  baseRefName headRefName headRefOid isCrossRepository maintainerCanModify
  headRepository { nameWithOwner }
  author { ...Who }
  mergeable mergeStateStatus reviewDecision
  additions deletions changedFiles
  labels(first: 100) { nodes { name } }
  reviewRequests(first: 20) {
    nodes {
      requestedReviewer {
        __typename
        ... on User { login }
        ... on Bot { login }
        ... on Team { slug }
      }
    }
  }
  commits(last: 20) {
    nodes { commit { oid committedDate parents(first: 2) { totalCount } } }
  }
  head: commits(last: 1) {
    nodes {
      commit {
        statusCheckRollup {
          contexts(first: 100) {
            pageInfo { hasNextPage endCursor }
            nodes { ...CheckContext }
          }
        }
      }
    }
  }
  latestOpinionatedReviews(first: 50, writersOnly: true) { nodes { ...ReviewFacts } }
  reviews(last: 50) { nodes { ...ReviewFacts } }
  reviewThreads(first: 100) {
    nodes {
      isResolved isOutdated
      comments(last: 1) { nodes { createdAt author { ...Who } } }
    }
  }
  comments(last: 50) {
    totalCount
    nodes { id databaseId createdAt body authorAssociation author { ...Who } }
  }
}
"""
    + _CHECK_CONTEXT
)

_OPEN_PULLS = (
    """
query($owner: String!, $name: String!, $after: String) {
  repository(owner: $owner, name: $name) {
    pullRequests(
      states: OPEN, first: 10, after: $after,
      orderBy: {field: CREATED_AT, direction: DESC}
    ) {
      pageInfo { hasNextPage endCursor }
      nodes { ...Facts }
    }
  }
}
"""
    + _FACTS
)

_ONE_PULL = (
    """
query($owner: String!, $name: String!, $number: Int!) {
  repository(owner: $owner, name: $name) {
    pullRequest(number: $number) { ...Facts }
  }
}
"""
    + _FACTS
)

_MORE_CONTEXTS = (
    """
query($owner: String!, $name: String!, $number: Int!, $after: String!) {
  repository(owner: $owner, name: $name) {
    pullRequest(number: $number) {
      commits(last: 1) {
        nodes {
          commit {
            statusCheckRollup {
              contexts(first: 100, after: $after) {
                pageInfo { hasNextPage endCursor }
                nodes { ...CheckContext }
              }
            }
          }
        }
      }
    }
  }
}
"""
    + _CHECK_CONTEXT
)

# Check run conclusions that let a required check pass. Everything else that has
# completed blocks, as it does in .github/actions/ci_gate.
_PASSING_CONCLUSIONS = frozenset({"SUCCESS", "NEUTRAL", "SKIPPED"})
_PENDING_STATUSES = frozenset({"PENDING", "EXPECTED"})


def parse_time(value: str) -> datetime:
    """Parse a GitHub timestamp.

    Args:
        value: An ISO 8601 timestamp such as ``2026-09-29T13:46:02Z``.

    Returns:
        The aware datetime (``fromisoformat`` only accepts ``Z`` from 3.11 on).
    """
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def same_login(first: str, second: str) -> bool:
    """Compare two logins the way GitHub does.

    Args:
        first: A login, from REST (``app[bot]``) or GraphQL (``app``).
        second: Another login.

    Returns:
        Whether they name the same account.
    """
    return (
        first.removesuffix("[bot]").casefold()
        == second.removesuffix("[bot]").casefold()
    )


@dataclasses.dataclass(frozen=True)
class Actor:
    """Who wrote something."""

    login: str
    is_bot: bool

    @property
    def display(self) -> str:
        """The login as GitHub shows it, with ``[bot]`` for apps."""
        return f"{self.login}[bot]" if self.is_bot else self.login


def _actor(node: dict[str, Any] | None) -> Actor:
    """Parse an actor node.

    Args:
        node: The node, or None for a deleted account.

    Returns:
        The actor; deleted accounts become GitHub's ``ghost``.
    """
    if node is None:
        return Actor("ghost", is_bot=False)
    return Actor(node["login"], is_bot=node["__typename"] == "Bot")


class CheckState(enum.Enum):
    """Where a status check stands."""

    PASSED = "passed"
    FAILED = "failed"
    PENDING = "pending"


@dataclasses.dataclass(frozen=True)
class Check:
    """The latest run of one status check on the head commit."""

    name: str
    state: CheckState


@dataclasses.dataclass(frozen=True)
class Review:
    """A submitted pull request review."""

    node_id: str
    author: Actor
    association: str
    state: str
    body: str
    submitted_at: datetime | None


@dataclasses.dataclass(frozen=True)
class Thread:
    """A review thread, by its latest comment."""

    resolved: bool
    outdated: bool
    last_author: Actor
    last_at: datetime


@dataclasses.dataclass(frozen=True)
class Comment:
    """A comment on the pull request's conversation tab."""

    node_id: str
    database_id: int
    author: Actor
    association: str
    body: str
    created_at: datetime


@dataclasses.dataclass(frozen=True)
class PullRequest:
    """Everything the triage rules read about one pull request."""

    number: int
    title: str
    body: str
    url: str
    author: Actor
    is_draft: bool
    base_ref: str
    head_ref: str
    head_sha: str
    head_repository: str | None
    cross_repository: bool
    maintainer_can_modify: bool
    mergeable: str
    merge_state: str
    review_decision: str | None
    additions: int
    deletions: int
    changed_files: int
    labels: frozenset[str]
    requested_reviewers: tuple[str, ...]
    # The newest commit that is not a merge: merging the base branch in is
    # neither new work to review nor an answer to review feedback.
    last_push_at: datetime
    checks: tuple[Check, ...]
    opinionated_reviews: tuple[Review, ...]
    reviews: tuple[Review, ...]
    threads: tuple[Thread, ...]
    comments: tuple[Comment, ...]
    comment_count: int

    @property
    def size(self) -> int:
        """Lines added plus lines deleted."""
        return self.additions + self.deletions


def _check(node: dict[str, Any]) -> tuple[str, CheckState, str]:
    """Parse a status check rollup context.

    Args:
        node: A CheckRun or StatusContext node.

    Returns:
        The check's name, its state, and the timestamp that orders reruns.
    """
    if node["__typename"] == "CheckRun":
        if node["status"] != "COMPLETED":
            state = CheckState.PENDING
        elif node["conclusion"] in _PASSING_CONCLUSIONS:
            state = CheckState.PASSED
        else:
            state = CheckState.FAILED
        # A queued rerun has no start time yet, and it supersedes the runs before it.
        return node["name"], state, node["startedAt"] or "9999"
    if node["state"] == "SUCCESS":
        state = CheckState.PASSED
    elif node["state"] in _PENDING_STATUSES:
        state = CheckState.PENDING
    else:
        state = CheckState.FAILED
    return node["context"], state, node["createdAt"]


def _latest_checks(nodes: list[dict[str, Any]]) -> tuple[Check, ...]:
    """Keep the latest run of each check.

    Args:
        nodes: Every context of the head commit's status check rollup.

    Returns:
        One check per name: the latest run, since a rerun replaces the result.
    """
    latest: dict[str, tuple[str, CheckState]] = {}
    for name, state, stamp in sorted(
        (_check(node) for node in nodes), key=operator.itemgetter(2)
    ):
        latest[name] = (stamp, state)
    return tuple(Check(name, state) for name, (_, state) in sorted(latest.items()))


def _review(node: dict[str, Any]) -> Review:
    """Parse a review node.

    Args:
        node: A PullRequestReview node.

    Returns:
        The review.
    """
    submitted = node["submittedAt"]
    return Review(
        node_id=node["id"],
        author=_actor(node["author"]),
        association=node["authorAssociation"],
        state=node["state"],
        body=node["body"] or "",
        submitted_at=parse_time(submitted) if submitted else None,
    )


def _requested_reviewer(node: dict[str, Any] | None) -> str | None:
    """Name a requested reviewer.

    Args:
        node: The requestedReviewer node.

    Returns:
        The user's or bot's login, or the team's slug; None for anything else.
    """
    if node is None:
        return None
    return node.get("login") or node.get("slug")


def parse(node: dict[str, Any]) -> PullRequest:
    """Turn a ``Facts`` node into a pull request.

    Args:
        node: The node, with its check contexts already complete.

    Returns:
        The pull request.
    """
    commits = [entry["commit"] for entry in node["commits"]["nodes"]]
    work = [commit for commit in commits if commit["parents"]["totalCount"] < 2]
    pushed = (work or commits)[-1]["committedDate"]
    rollup = node["head"]["nodes"][0]["commit"]["statusCheckRollup"]
    head_repository = node["headRepository"]
    threads = []
    for thread in node["reviewThreads"]["nodes"]:
        last = thread["comments"]["nodes"]
        if not last:
            continue
        threads.append(
            Thread(
                resolved=thread["isResolved"],
                outdated=thread["isOutdated"],
                last_author=_actor(last[0]["author"]),
                last_at=parse_time(last[0]["createdAt"]),
            )
        )
    reviewers = (
        _requested_reviewer(request["requestedReviewer"])
        for request in node["reviewRequests"]["nodes"]
    )
    return PullRequest(
        number=node["number"],
        title=node["title"],
        body=node["body"] or "",
        url=node["url"],
        author=_actor(node["author"]),
        is_draft=node["isDraft"],
        base_ref=node["baseRefName"],
        head_ref=node["headRefName"],
        head_sha=node["headRefOid"],
        head_repository=head_repository["nameWithOwner"] if head_repository else None,
        cross_repository=node["isCrossRepository"],
        maintainer_can_modify=node["maintainerCanModify"],
        mergeable=node["mergeable"],
        merge_state=node["mergeStateStatus"],
        review_decision=node["reviewDecision"],
        additions=node["additions"],
        deletions=node["deletions"],
        changed_files=node["changedFiles"],
        labels=frozenset(label["name"] for label in node["labels"]["nodes"]),
        requested_reviewers=tuple(name for name in reviewers if name),
        last_push_at=parse_time(pushed),
        checks=_latest_checks(rollup["contexts"]["nodes"]) if rollup else (),
        opinionated_reviews=tuple(
            _review(review)
            for review in node["latestOpinionatedReviews"]["nodes"]
            if review["submittedAt"]
        ),
        reviews=tuple(
            _review(review)
            for review in node["reviews"]["nodes"]
            if review["submittedAt"]
        ),
        threads=tuple(threads),
        comments=tuple(
            Comment(
                node_id=comment["id"],
                database_id=comment["databaseId"],
                author=_actor(comment["author"]),
                association=comment["authorAssociation"],
                body=comment["body"],
                created_at=parse_time(comment["createdAt"]),
            )
            for comment in node["comments"]["nodes"]
        ),
        comment_count=node["comments"]["totalCount"],
    )


def _complete_contexts(github: GitHub, node: dict[str, Any]) -> dict[str, Any]:
    """Fetch the check contexts a ``Facts`` node was cut off at.

    The first page holds 100 contexts, and a pull request to main reports more: a
    gate that sorts past the page would otherwise look like it never reported.

    Args:
        github: The client.
        node: A ``Facts`` node; its context list is extended in place.

    Returns:
        The same node.
    """
    rollup = node["head"]["nodes"][0]["commit"]["statusCheckRollup"]
    if rollup is None:
        return node
    contexts = rollup["contexts"]
    while contexts["pageInfo"]["hasNextPage"]:
        data = github.graphql(
            _MORE_CONTEXTS,
            owner=github.owner,
            name=github.name,
            number=node["number"],
            after=contexts["pageInfo"]["endCursor"],
        )
        page = data["repository"]["pullRequest"]["commits"]["nodes"][0]["commit"]
        page = page["statusCheckRollup"]["contexts"]
        contexts["nodes"].extend(page["nodes"])
        contexts["pageInfo"] = page["pageInfo"]
    return node


def fetch(github: GitHub, number: int) -> PullRequest:
    """Fetch one pull request.

    Args:
        github: The client.
        number: The pull request number.

    Returns:
        The pull request.
    """
    data = github.graphql(
        _ONE_PULL, owner=github.owner, name=github.name, number=number
    )
    return parse(_complete_contexts(github, data["repository"]["pullRequest"]))


def fetch_open(github: GitHub) -> Iterator[PullRequest]:
    """Fetch every open pull request, newest first.

    Args:
        github: The client.

    Yields:
        Each open pull request.
    """
    for node in github.graphql_nodes(
        _OPEN_PULLS,
        "repository",
        "pullRequests",
        owner=github.owner,
        name=github.name,
    ):
        yield parse(_complete_contexts(github, node))
