"""Unit tests for scripts/pr_bot/pulls.py (the facts the triage rules read)."""

from __future__ import annotations

import copy
from typing import Any

from scripts.pr_bot import pulls
from scripts.pr_bot.pulls import Actor, Check, CheckState
from tests.units.pr_bot.conftest import FakeGitHub, at


def who(login: str, kind: str = "User") -> dict[str, str]:
    """Build an actor node.

    Args:
        login: The login.
        kind: The actor's GraphQL type.

    Returns:
        The node.
    """
    return {"__typename": kind, "login": login}


def check_run(
    name: str,
    status: str = "COMPLETED",
    conclusion: str | None = "SUCCESS",
    started: str | None = "2026-09-01T00:00:00Z",
) -> dict[str, Any]:
    """Build a CheckRun node.

    Args:
        name: The check's name.
        status: Its status.
        conclusion: Its conclusion, once completed.
        started: When it started, or None while queued.

    Returns:
        The node.
    """
    return {
        "__typename": "CheckRun",
        "name": name,
        "status": status,
        "conclusion": conclusion,
        "startedAt": started,
    }


def facts_node(**changes: Any) -> dict[str, Any]:
    """Build a Facts node the way GitHub's GraphQL API returns it.

    Args:
        **changes: Top-level fields to override.

    Returns:
        The node.
    """
    node: dict[str, Any] = {
        "number": 7,
        "title": "Fix the thing",
        "body": None,
        "url": "https://github.com/reflex-dev/reflex/pull/7",
        "isDraft": False,
        "baseRefName": "main",
        "headRefName": "fix-thing",
        "headRefOid": "a" * 40,
        "isCrossRepository": True,
        "maintainerCanModify": True,
        "headRepository": {"nameWithOwner": "contributor/reflex"},
        "author": who("contributor"),
        "mergeable": "MERGEABLE",
        "mergeStateStatus": "BLOCKED",
        "reviewDecision": "REVIEW_REQUIRED",
        "additions": 10,
        "deletions": 3,
        "changedFiles": 2,
        "labels": {"nodes": [{"name": "on deck"}]},
        "reviewRequests": {
            "nodes": [
                {"requestedReviewer": {"__typename": "User", "login": "masenf"}},
                {"requestedReviewer": {"__typename": "Team", "slug": "reflex-team"}},
                {"requestedReviewer": {"__typename": "Mannequin"}},
            ]
        },
        "commits": {
            "nodes": [
                {
                    "commit": {
                        "oid": "1",
                        "committedDate": "2026-09-01T01:00:00Z",
                        "parents": {"totalCount": 1},
                    }
                },
                {
                    "commit": {
                        "oid": "2",
                        "committedDate": "2026-09-01T02:00:00Z",
                        "parents": {"totalCount": 2},
                    }
                },
            ]
        },
        "head": {
            "nodes": [
                {
                    "commit": {
                        "statusCheckRollup": {
                            "contexts": {
                                "pageInfo": {"hasNextPage": False, "endCursor": None},
                                "nodes": [check_run("unit-tests-gate")],
                            }
                        }
                    }
                }
            ]
        },
        "latestOpinionatedReviews": {"nodes": []},
        "reviews": {
            "nodes": [
                {
                    "id": "R_1",
                    "state": "COMMENTED",
                    "body": "",
                    "submittedAt": "2026-09-01T03:00:00Z",
                    "authorAssociation": "MEMBER",
                    "author": who("maintainer"),
                },
                {
                    "id": "R_2",
                    "state": "PENDING",
                    "body": "draft",
                    "submittedAt": None,
                    "authorAssociation": "MEMBER",
                    "author": who("maintainer"),
                },
            ]
        },
        "reviewThreads": {
            "nodes": [
                {
                    "isResolved": False,
                    "isOutdated": False,
                    "comments": {
                        "nodes": [
                            {
                                "createdAt": "2026-09-01T04:00:00Z",
                                "author": who("greptile-apps", "Bot"),
                            }
                        ]
                    },
                },
                {"isResolved": False, "isOutdated": False, "comments": {"nodes": []}},
            ]
        },
        "comments": {
            "totalCount": 60,
            "nodes": [
                {
                    "id": "IC_1",
                    "databaseId": 11,
                    "createdAt": "2026-09-01T05:00:00Z",
                    "body": "hello",
                    "authorAssociation": "NONE",
                    "author": None,
                }
            ],
        },
    }
    node.update(changes)
    return node


def test_parse_reads_every_fact():
    pr = pulls.parse(facts_node())
    assert pr.number == 7
    assert pr.body == ""
    assert pr.author == Actor("contributor", is_bot=False)
    assert pr.head_repository == "contributor/reflex"
    assert pr.labels == frozenset({"on deck"})
    assert pr.requested_reviewers == ("masenf", "reflex-team")
    assert pr.size == 13
    assert pr.checks == (Check("unit-tests-gate", CheckState.PASSED),)
    # The pending review has not been submitted; it is not part of the record.
    assert [r.node_id for r in pr.reviews] == ["R_1"]
    # A thread whose comments are all deleted has nothing to wait on.
    assert len(pr.threads) == 1
    assert pr.threads[0].last_author == Actor("greptile-apps", is_bot=True)
    assert pr.threads[0].last_author.display == "greptile-apps[bot]"
    assert pr.comments[0].author.login == "ghost"
    assert pr.comment_count == 60


def test_last_push_skips_merge_commits():
    assert pulls.parse(facts_node()).last_push_at == at(1)


def test_last_push_of_only_merges_is_the_newest_commit():
    node = facts_node()
    for entry in node["commits"]["nodes"]:
        entry["commit"]["parents"]["totalCount"] = 2
    assert pulls.parse(node).last_push_at == at(2)


def test_a_rerun_replaces_the_earlier_result():
    node = facts_node()
    node["head"]["nodes"][0]["commit"]["statusCheckRollup"]["contexts"]["nodes"] = [
        check_run("tests", conclusion="FAILURE", started="2026-09-01T01:00:00Z"),
        check_run("tests", conclusion="SUCCESS", started="2026-09-01T02:00:00Z"),
        check_run("lint", conclusion="SUCCESS", started="2026-09-01T01:00:00Z"),
        # A queued rerun has not started, and it supersedes the success before it.
        check_run("lint", status="QUEUED", conclusion=None, started=None),
        check_run("skipped", conclusion="SKIPPED"),
        check_run("cancelled", conclusion="CANCELLED"),
        {
            "__typename": "StatusContext",
            "context": "ci/legacy",
            "state": "ERROR",
            "createdAt": "2026-09-01T01:00:00Z",
        },
        {
            "__typename": "StatusContext",
            "context": "ci/expected",
            "state": "EXPECTED",
            "createdAt": "2026-09-01T01:00:00Z",
        },
    ]
    checks = {c.name: c.state for c in pulls.parse(node).checks}
    assert checks == {
        "tests": CheckState.PASSED,
        "lint": CheckState.PENDING,
        "skipped": CheckState.PASSED,
        "cancelled": CheckState.FAILED,
        "ci/legacy": CheckState.FAILED,
        "ci/expected": CheckState.PENDING,
    }


def test_no_status_checks_at_all():
    node = facts_node()
    node["head"]["nodes"][0]["commit"]["statusCheckRollup"] = None
    assert pulls.parse(node).checks == ()


def test_same_login_matches_rest_and_graphql_spellings():
    assert pulls.same_login("Greptile-Apps[bot]", "greptile-apps")
    assert not pulls.same_login("masenf", "masen")


def test_fetch_completes_check_contexts_past_the_first_page():
    github = FakeGitHub()
    first = facts_node()
    contexts = first["head"]["nodes"][0]["commit"]["statusCheckRollup"]["contexts"]
    contexts["pageInfo"] = {"hasNextPage": True, "endCursor": "c1"}
    seen = []

    def answer(query: str, variables: dict[str, Any]) -> Any:
        seen.append(variables)
        if "after" not in variables:
            return {"repository": {"pullRequest": copy.deepcopy(first)}}
        page = {
            "pageInfo": {"hasNextPage": False, "endCursor": None},
            "nodes": [check_run("pre-commit", conclusion="FAILURE")],
        }
        return {
            "repository": {
                "pullRequest": {
                    "commits": {
                        "nodes": [{"commit": {"statusCheckRollup": {"contexts": page}}}]
                    }
                }
            }
        }

    github.graphql_handler = answer
    pr = pulls.fetch(github, 7)
    assert {c.name: c.state for c in pr.checks} == {
        "unit-tests-gate": CheckState.PASSED,
        "pre-commit": CheckState.FAILED,
    }
    assert seen[1] == {
        "owner": "reflex-dev",
        "name": "reflex",
        "number": 7,
        "after": "c1",
    }


def test_fetch_open_pages_through_every_pull_request():
    github = FakeGitHub()
    pages = {
        None: ([facts_node(number=1)], {"hasNextPage": True, "endCursor": "p1"}),
        "p1": ([facts_node(number=2)], {"hasNextPage": False, "endCursor": None}),
    }

    def answer(query: str, variables: dict[str, Any]) -> Any:
        nodes, info = pages[variables["after"]]
        return {"repository": {"pullRequests": {"nodes": nodes, "pageInfo": info}}}

    github.graphql_handler = answer
    assert [pr.number for pr in pulls.fetch_open(github)] == [1, 2]
