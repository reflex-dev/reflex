"""Decide whose turn it is on a pull request.

The rules read GitHub's own records (draft state, mergeability, the required checks,
reviews, review threads and who acted last), so the same pull request always gets the
same answer. The one judgment they cannot make, whether a maintainer's comment asks
the author for something, comes from Claude and is passed in.

A pull request is waiting on its submitter when the next move is plainly theirs: it
is a draft, it conflicts with its base branch, a required check fails, or review
feedback is newer than their last commit or reply. It is ready to merge when it is
approved, every required check passed and nothing changed since the approval. Every
other pull request is waiting on a maintainer.
"""

from __future__ import annotations

import dataclasses
import enum
import json
from collections.abc import Iterable, Mapping
from datetime import datetime
from pathlib import Path

from scripts.pr_bot import comments
from scripts.pr_bot.pulls import Actor, CheckState, PullRequest, Thread, same_login

RULESET = (
    Path(__file__).parents[2] / ".github" / "rulesets" / "main-required-checks.json"
)
# The branch the ruleset protects; pull requests to other branches have every check
# treated as required.
DEFAULT_BRANCH = "main"
# Commenters whose words carry a maintainer's weight.
MAINTAINER_ASSOCIATIONS = frozenset({"OWNER", "MEMBER", "COLLABORATOR"})


class Status(enum.Enum):
    """Whose turn it is."""

    READY = "ready to merge"
    MAINTAINER = "waiting on maintainer"
    SUBMITTER = "waiting on submitter"

    @property
    def label(self) -> str:
        """The label that marks a pull request with this status."""
        return f"status: {self.value}"


@dataclasses.dataclass(frozen=True)
class Verdict:
    """A status and the facts that decided it."""

    status: Status
    reasons: tuple[str, ...]


@dataclasses.dataclass(frozen=True)
class Request:
    """A maintainer's comment that may ask the author for something."""

    node_id: str
    author: Actor
    body: str


def required_checks(ruleset: Path = RULESET) -> frozenset[str]:
    """Read the checks the default branch's ruleset requires.

    Args:
        ruleset: The ruleset file, in the format GitHub imports.

    Returns:
        The required check names.
    """
    document = json.loads(ruleset.read_text(encoding="utf-8"))
    return frozenset(
        check["context"]
        for rule in document["rules"]
        if rule["type"] == "required_status_checks"
        for check in rule["parameters"]["required_status_checks"]
    )


def _is_author(pr: PullRequest, actor: Actor) -> bool:
    """Tell whether an actor opened the pull request.

    Args:
        pr: The pull request.
        actor: Who wrote something on it.

    Returns:
        Whether that is the pull request's author.
    """
    return same_login(actor.login, pr.author.login)


def author_activity(pr: PullRequest) -> datetime:
    """Return when the author last moved the pull request forward.

    Args:
        pr: The pull request.

    Returns:
        The latest of their last non-merge commit, comment, review and thread reply.
    """
    times = [pr.last_push_at]
    times.extend(c.created_at for c in pr.comments if _is_author(pr, c.author))
    times.extend(
        r.submitted_at
        for r in pr.reviews
        if r.submitted_at and _is_author(pr, r.author)
    )
    times.extend(t.last_at for t in pr.threads if _is_author(pr, t.last_author))
    return max(times)


def _is_maintainer(pr: PullRequest, author: Actor, association: str) -> bool:
    """Tell whether someone other than the author speaks as a maintainer.

    Args:
        pr: The pull request.
        author: Who wrote the comment.
        association: Their relationship to the repository.

    Returns:
        Whether they are a person with write access who did not open the pull request.
    """
    return (
        not author.is_bot
        and association in MAINTAINER_ASSOCIATIONS
        and not _is_author(pr, author)
    )


def requests_to_judge(pr: PullRequest) -> list[Request]:
    """Find maintainers' comments that are newer than the author's last move.

    Each may ask the author for something or may not ("thanks", "cc @someone"), which
    only reading it can tell. Reviews that request changes are left out: their state
    already says so.

    Args:
        pr: The pull request.

    Returns:
        The comments and review bodies to judge.
    """
    since = author_activity(pr)
    found = [
        Request(comment.node_id, comment.author, comment.body)
        for comment in pr.comments
        if comment.created_at > since
        and comment.body.strip()
        and _is_maintainer(pr, comment.author, comment.association)
    ]
    found.extend(
        Request(review.node_id, review.author, review.body)
        for review in pr.reviews
        if review.state in ("COMMENTED", "APPROVED")
        and review.submitted_at
        and review.submitted_at > since
        and review.body.strip()
        and _is_maintainer(pr, review.author, review.association)
    )
    return found


def gating_checks(
    pr: PullRequest, required: frozenset[str]
) -> tuple[list[str], list[str]]:
    """Find the checks that keep the pull request from merging.

    Args:
        pr: The pull request.
        required: The checks the default branch requires.

    Returns:
        The failing checks and the checks that have not finished (or not reported).
    """
    states = {check.name: check.state for check in pr.checks}
    names = sorted(required) if pr.base_ref == DEFAULT_BRANCH else sorted(states)
    failing = [name for name in names if states.get(name) is CheckState.FAILED]
    pending = [
        name
        for name in names
        if states.get(name, CheckState.PENDING) is CheckState.PENDING
    ]
    return failing, pending


def _awaits_author(pr: PullRequest, thread: Thread) -> bool:
    """Tell whether a review thread waits on the author.

    Args:
        pr: The pull request.
        thread: One of its review threads.

    Returns:
        Whether the thread is open on current code, someone else spoke last, and the
        author has not pushed since. Bots' threads count like people's.
    """
    return (
        not thread.resolved
        and not thread.outdated
        and not _is_author(pr, thread.last_author)
        and thread.last_at > pr.last_push_at
    )


def _plural(count: int, singular: str, plural: str) -> str:
    """Pick the word form for a count.

    Args:
        count: How many.
        singular: The phrase for one.
        plural: The phrase for several.

    Returns:
        The count followed by the matching phrase.
    """
    return f"{count} {singular if count == 1 else plural}"


def _names(names: Iterable[str]) -> str:
    """Join names for a sentence.

    Args:
        names: Logins or check names.

    Returns:
        The names separated by commas.
    """
    return ", ".join(names)


def _review_needed(pr: PullRequest) -> str:
    """Say who the pull request waits on for a review.

    Args:
        pr: A pull request without an approval.

    Returns:
        The reason.
    """
    if pr.requested_reviewers:
        return f"Waiting for a review from {_names(pr.requested_reviewers)}."
    if any(
        _is_maintainer(pr, review.author, review.association) for review in pr.reviews
    ):
        return "It needs an approving review."
    return "No maintainer has reviewed it yet."


def classify(
    pr: PullRequest, required: frozenset[str], asks_author: Mapping[str, bool]
) -> Verdict:
    """Decide whose turn it is.

    Args:
        pr: The pull request.
        required: The checks the default branch requires.
        asks_author: For each judged request (by node id), whether it asks the author
            for something. Unjudged requests count as not asking.

    Returns:
        The status and its reasons.
    """
    if pr.is_draft:
        return Verdict(Status.SUBMITTER, ("It is a draft.",))
    since = author_activity(pr)
    on_submitter: list[str] = []
    on_maintainer: list[str] = []

    if pr.mergeable == "CONFLICTING":
        on_submitter.append(f"It has merge conflicts with `{pr.base_ref}`.")
    failing, pending = gating_checks(pr, required)
    if failing:
        on_submitter.append(f"Required checks are failing: {comments.code(failing)}.")
    changes = [r for r in pr.opinionated_reviews if r.state == "CHANGES_REQUESTED"]
    for review in changes:
        if review.submitted_at and review.submitted_at > since:
            on_submitter.append(f"{review.author.display} requested changes.")
        else:
            on_maintainer.append(
                f"{review.author.display} requested changes, and the author has "
                "responded since."
            )
    waiting = sum(1 for thread in pr.threads if _awaits_author(pr, thread))
    if waiting:
        threads = _plural(
            waiting,
            "unresolved review thread awaits",
            "unresolved review threads await",
        )
        on_submitter.append(f"{threads} the author's reply or a new commit.")
    askers = sorted({
        request.author.display
        for request in requests_to_judge(pr)
        if asks_author.get(request.node_id)
    })
    if askers:
        on_submitter.append(f"{_names(askers)} asked for changes in a comment.")
    if on_submitter:
        return Verdict(Status.SUBMITTER, tuple(on_submitter))

    approvals = [r for r in pr.opinionated_reviews if r.state == "APPROVED"]
    approved = pr.review_decision == "APPROVED" or (
        pr.review_decision is None and bool(approvals) and not changes
    )
    approved_at = max(
        (r.submitted_at for r in approvals if r.submitted_at), default=None
    )
    if not approved:
        if not changes:
            on_maintainer.append(_review_needed(pr))
    elif approved_at is not None and pr.last_push_at > approved_at:
        on_maintainer.append("Commits were pushed after the latest approval.")
    replied = sum(
        1
        for thread in pr.threads
        if not thread.resolved
        and not thread.outdated
        and _is_author(pr, thread.last_author)
        and (approved_at is None or thread.last_at > approved_at)
    )
    if replied:
        threads = _plural(
            replied, "unresolved review thread has", "unresolved review threads have"
        )
        on_maintainer.append(f"{threads} a reply from the author.")
    if pending:
        on_maintainer.append(
            f"Required checks have not passed yet: {comments.code(pending)}."
        )
    if approved and not on_maintainer and pr.mergeable == "UNKNOWN":
        # GitHub computes mergeability lazily; the next sweep sees the answer.
        on_maintainer.append("GitHub has not finished checking it for conflicts.")
    if approved and not on_maintainer and pr.merge_state in ("BLOCKED", "BEHIND"):
        on_maintainer.append(
            "It is approved, but GitHub still blocks the merge "
            f"(merge state `{pr.merge_state}`)."
        )
    if on_maintainer:
        return Verdict(Status.MAINTAINER, tuple(on_maintainer))

    approvers = sorted({review.author.display for review in approvals})
    return Verdict(
        Status.READY,
        (
            f"Approved by {_names(approvers)}." if approvers else "Approved.",
            "Required checks passed.",
            "No merge conflicts.",
        ),
    )
