"""Unit tests for scripts/pr_bot/status.py (whose turn it is on a pull request)."""

from __future__ import annotations

from scripts.pr_bot import status
from scripts.pr_bot.pulls import Check, CheckState
from scripts.pr_bot.status import Status
from tests.units.pr_bot.conftest import (
    AUTHOR,
    GREPTILE,
    MAINTAINER,
    at,
    comment,
    pull_request,
    review,
    thread,
)

REQUIRED = frozenset({"unit-tests-gate", "pre-commit"})
GREEN = (
    Check("unit-tests-gate", CheckState.PASSED),
    Check("pre-commit", CheckState.PASSED),
)
APPROVAL = review(MAINTAINER, "APPROVED", 2)


def classify(asks_author=None, **changes):
    """Classify a pull request whose required checks pass unless overridden.

    Args:
        asks_author: Judgments of maintainers' comments, by node id.
        **changes: Fields of the pull request to override.

    Returns:
        The verdict.
    """
    return status.classify(
        pull_request(**{"checks": GREEN, **changes}), REQUIRED, asks_author or {}
    )


def test_required_checks_come_from_the_ruleset():
    required = status.required_checks()
    assert {"unit-tests-gate", "pre-commit", "changelog"} <= required


def test_new_pull_request_waits_on_maintainer():
    verdict = classify()
    assert verdict.status is Status.MAINTAINER
    assert verdict.reasons == ("No maintainer has reviewed it yet.",)


def test_requested_reviewers_are_named():
    verdict = classify(requested_reviewers=("masenf", "reflex-team"))
    assert verdict.reasons == ("Waiting for a review from masenf, reflex-team.",)


def test_draft_waits_on_submitter():
    verdict = classify(is_draft=True, mergeable="CONFLICTING")
    assert verdict.status is Status.SUBMITTER
    assert verdict.reasons == ("It is a draft.",)


def test_conflicts_wait_on_submitter():
    verdict = classify(mergeable="CONFLICTING", review_decision="APPROVED")
    assert verdict.status is Status.SUBMITTER
    assert verdict.reasons == ("It has merge conflicts with `main`.",)


def test_failing_required_check_waits_on_submitter():
    checks = (
        Check("unit-tests-gate", CheckState.FAILED),
        Check("pre-commit", CheckState.PASSED),
    )
    verdict = classify(checks=checks)
    assert verdict.status is Status.SUBMITTER
    assert verdict.reasons == ("Required checks are failing: `unit-tests-gate`.",)


def test_failing_optional_check_is_ignored():
    checks = (*GREEN, Check("CodSpeed", CheckState.FAILED))
    assert classify(checks=checks).status is Status.MAINTAINER


def test_missing_required_check_counts_as_pending():
    verdict = classify(
        checks=(Check("pre-commit", CheckState.PASSED),),
        review_decision="APPROVED",
        opinionated_reviews=(APPROVAL,),
    )
    assert verdict.status is Status.MAINTAINER
    assert verdict.reasons == (
        "Required checks have not passed yet: `unit-tests-gate`.",
    )


def test_other_base_branches_require_every_check():
    checks = (Check("anything", CheckState.FAILED),)
    verdict = classify(base_ref="r/pre-0.9.13", checks=checks)
    assert verdict.status is Status.SUBMITTER
    assert verdict.reasons == ("Required checks are failing: `anything`.",)


def test_changes_requested_after_last_push_wait_on_submitter():
    changes = review(MAINTAINER, "CHANGES_REQUESTED", 1)
    verdict = classify(opinionated_reviews=(changes,), reviews=(changes,))
    assert verdict.status is Status.SUBMITTER
    assert verdict.reasons == ("maintainer requested changes.",)


def test_changes_requested_then_answered_waits_on_maintainer():
    changes = review(MAINTAINER, "CHANGES_REQUESTED", 1)
    verdict = classify(opinionated_reviews=(changes,), last_push_at=at(5))
    assert verdict.status is Status.MAINTAINER
    assert verdict.reasons == (
        "maintainer requested changes, and the author has responded since.",
    )


def test_a_reply_from_the_author_counts_as_responding():
    changes = review(MAINTAINER, "CHANGES_REQUESTED", 1)
    reply = comment(AUTHOR, 2, association="CONTRIBUTOR")
    verdict = classify(opinionated_reviews=(changes,), comments=(reply,))
    assert verdict.status is Status.MAINTAINER


def test_merge_commits_do_not_answer_review_feedback():
    # last_push_at already excludes merges (see test_pulls), so a merge of main
    # after the review leaves the feedback unanswered.
    changes = review(MAINTAINER, "CHANGES_REQUESTED", 1)
    verdict = classify(opinionated_reviews=(changes,))
    assert verdict.status is Status.SUBMITTER


def test_open_thread_newer_than_last_push_waits_on_submitter():
    verdict = classify(threads=(thread(MAINTAINER, 1),))
    assert verdict.status is Status.SUBMITTER
    assert verdict.reasons == (
        "1 unresolved review thread awaits the author's reply or a new commit.",
    )


def test_ai_reviewer_threads_count_like_people():
    verdict = classify(threads=(thread(GREPTILE, 1), thread(GREPTILE, 2)))
    assert verdict.status is Status.SUBMITTER
    assert verdict.reasons == (
        "2 unresolved review threads await the author's reply or a new commit.",
    )


def test_resolved_outdated_and_older_threads_do_not_wait():
    threads = (
        thread(MAINTAINER, 1, resolved=True),
        thread(MAINTAINER, 1, outdated=True),
        thread(MAINTAINER, -1),
    )
    assert classify(threads=threads).status is Status.MAINTAINER


def test_thread_the_author_answered_waits_on_maintainer():
    verdict = classify(threads=(thread(AUTHOR, 1),))
    assert verdict.status is Status.MAINTAINER
    assert verdict.reasons == (
        "No maintainer has reviewed it yet.",
        "1 unresolved review thread has a reply from the author.",
    )


def test_maintainer_comment_judged_as_a_request_waits_on_submitter():
    note = comment(MAINTAINER, 1, "Could you add a test for this?")
    verdict = classify(comments=(note,), asks_author={note.node_id: True})
    assert verdict.status is Status.SUBMITTER
    assert verdict.reasons == ("maintainer asked for changes in a comment.",)


def test_maintainer_comment_judged_otherwise_or_unjudged_does_not():
    note = comment(MAINTAINER, 1, "Thanks, looking at it this week.")
    assert classify(comments=(note,), asks_author={note.node_id: False}).status is (
        Status.MAINTAINER
    )
    assert classify(comments=(note,)).status is Status.MAINTAINER


def test_requests_to_judge_are_maintainer_comments_since_the_author_acted():
    pr = pull_request(
        comments=(
            comment(MAINTAINER, -1, "old"),
            comment(MAINTAINER, 2, "new"),
            comment(MAINTAINER, 3, "  "),
            comment(AUTHOR, 1, "mine", association="CONTRIBUTOR"),
            comment(GREPTILE, 2, "bot", association="NONE"),
            comment(MAINTAINER, 2, "outsider", association="CONTRIBUTOR"),
        ),
        reviews=(
            review(MAINTAINER, "COMMENTED", 2, "Please rename this."),
            review(MAINTAINER, "APPROVED", 2, "LGTM once the docs are updated."),
            review(MAINTAINER, "CHANGES_REQUESTED", 2, "Needs work."),
            review(MAINTAINER, "COMMENTED", 2, ""),
        ),
    )
    bodies = [request.body for request in status.requests_to_judge(pr)]
    assert bodies == ["new", "Please rename this.", "LGTM once the docs are updated."]


def test_approved_and_green_is_ready():
    verdict = classify(review_decision="APPROVED", opinionated_reviews=(APPROVAL,))
    assert verdict.status is Status.READY
    assert verdict.reasons == (
        "Approved by maintainer.",
        "Required checks passed.",
        "No merge conflicts.",
    )


def test_approval_without_required_reviews_counts():
    verdict = classify(review_decision=None, opinionated_reviews=(APPROVAL,))
    assert verdict.status is Status.READY


def test_commits_after_the_approval_need_another_look():
    verdict = classify(
        review_decision="APPROVED", opinionated_reviews=(APPROVAL,), last_push_at=at(4)
    )
    assert verdict.status is Status.MAINTAINER
    assert verdict.reasons == ("Commits were pushed after the latest approval.",)


def test_author_reply_after_the_approval_needs_another_look():
    verdict = classify(
        review_decision="APPROVED",
        opinionated_reviews=(APPROVAL,),
        threads=(thread(AUTHOR, 3),),
    )
    assert verdict.status is Status.MAINTAINER
    assert verdict.reasons == (
        "1 unresolved review thread has a reply from the author.",
    )


def test_author_reply_before_the_approval_is_settled():
    verdict = classify(
        review_decision="APPROVED",
        opinionated_reviews=(APPROVAL,),
        threads=(thread(AUTHOR, 1),),
    )
    assert verdict.status is Status.READY


def test_approved_but_blocked_by_github_waits_on_maintainer():
    verdict = classify(
        review_decision="APPROVED",
        opinionated_reviews=(APPROVAL,),
        merge_state="BLOCKED",
    )
    assert verdict.status is Status.MAINTAINER
    assert verdict.reasons == (
        "It is approved, but GitHub still blocks the merge (merge state `BLOCKED`).",
    )


def test_labels_are_prefixed():
    assert {s.label for s in Status} == {
        "status: ready to merge",
        "status: waiting on maintainer",
        "status: waiting on submitter",
    }


def test_approved_but_mergeability_unknown_waits_for_the_next_look():
    verdict = classify(
        review_decision="APPROVED",
        opinionated_reviews=(APPROVAL,),
        mergeable="UNKNOWN",
    )
    assert verdict.status is Status.MAINTAINER
    assert verdict.reasons == ("GitHub has not finished checking it for conflicts.",)
