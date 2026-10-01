"""Unit tests for scripts/pr_bot/triage.py (labels, comment and state)."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest

from scripts.pr_bot import comments, pulls, triage
from scripts.pr_bot.github import GitHubError
from scripts.pr_bot.llm import ClaudeError
from scripts.pr_bot.pulls import Actor, PullRequest
from tests.units.pr_bot.conftest import (
    AUTHOR,
    MAINTAINER,
    FakeClaude,
    FakeGitHub,
    comment,
    pull_request,
)

BOT = Actor("github-actions", is_bot=True)
REPO = "repos/reflex-dev/reflex"
REQUIRED = frozenset({"unit-tests-gate"})
ESTIMATE = {"complexity": "medium", "rationale": "Changes one CLI command."}


def github_for(labels: tuple[str, ...] = tuple(triage.LABELS)) -> FakeGitHub:
    """Create a fake GitHub where pull request 7's files and diff can be read.

    Args:
        labels: The labels the repository defines.

    Returns:
        The fake.
    """
    github = FakeGitHub()
    github.route("GET", f"{REPO}/labels", [{"name": name} for name in labels])
    github.route(
        "GET",
        f"{REPO}/pulls/7/files",
        [
            {
                "filename": "reflex/app.py",
                "status": "modified",
                "additions": 10,
                "deletions": 2,
            }
        ],
    )
    github.route(
        "DIFF", f"{REPO}/pulls/7", "diff --git a/reflex/app.py b/reflex/app.py\n+x\n"
    )
    return github


def runner(
    github: FakeGitHub, claude: FakeClaude | None, estimates: int = 5
) -> triage.Triage:
    """Create a triage runner that writes to the fake.

    Args:
        github: The fake GitHub.
        claude: The fake Claude, or None.
        estimates: How many complexity estimates it may make.

    Returns:
        The runner.
    """
    return triage.Triage(
        github=github,
        claude=claude,
        required=REQUIRED,
        estimates_left=estimates,
        write=comments.writer(dry_run=False),
    )


def created_comment(github: FakeGitHub) -> str:
    """Find the one comment the run posted on pull request 7.

    Args:
        github: The fake GitHub.

    Returns:
        The comment's body.
    """
    (body,) = [
        request[2]["body"]
        for request in github.writes()
        if request[:2] == ("POST", f"{REPO}/issues/7/comments")
    ]
    return body


def test_first_triage_labels_estimates_and_comments():
    github = github_for(labels=())
    claude = FakeClaude(ESTIMATE)
    runner(github, claude).triage(pull_request())
    writes = github.writes()
    assert (
        "POST",
        f"{REPO}/labels",
        {
            "name": "complexity: medium",
            "color": "bfd4f2",
            "description": triage.LABELS["complexity: medium"][1],
        },
    ) in writes
    assert (
        "POST",
        f"{REPO}/issues/7/labels",
        {"labels": ["complexity: medium", "status: waiting on maintainer"]},
    ) in writes
    body = created_comment(github)
    assert body.startswith(comments.marker("triage"))
    assert "**Status: waiting on maintainer**" in body
    assert "- No maintainer has reviewed it yet." in body
    assert "**Complexity: medium**. Changes one CLI command." in body
    assert comments.decode_state(body) == {
        "complexity": "medium",
        "rationale": "Changes one CLI command.",
        "size": 12,
    }


def test_second_triage_changes_nothing_and_asks_nothing():
    first = github_for()
    runner(first, FakeClaude(ESTIMATE)).triage(pull_request())
    body = created_comment(first)
    labelled = pull_request(
        labels=frozenset({"status: waiting on maintainer", "complexity: medium"}),
        comments=(comment(BOT, 1, body, association="NONE"),),
        comment_count=1,
    )
    github = github_for()
    claude = FakeClaude()
    runner(github, claude).triage(labelled)
    assert github.writes() == []
    assert claude.calls == []


def test_draft_is_labeled_without_a_comment_or_claude():
    github = github_for()
    claude = FakeClaude()
    runner(github, claude).triage(
        pull_request(is_draft=True, comments=(comment(MAINTAINER, 5, "please fix"),))
    )
    assert github.writes() == [
        (
            "POST",
            f"{REPO}/issues/7/labels",
            {"labels": ["status: waiting on submitter"]},
        )
    ]
    assert claude.calls == []


def test_a_maintainers_complexity_label_stands():
    github = github_for()
    claude = FakeClaude()
    runner(github, claude).triage(pull_request(labels=frozenset({"complexity: high"})))
    assert claude.calls == []
    assert not any(w[0] == "DELETE" for w in github.writes())
    assert "**Complexity: high** (set by a maintainer)." in created_comment(github)


def test_a_pull_request_that_doubled_is_estimated_again():
    state = comments.encode_state({"complexity": "low", "size": 10})
    existing = comment(
        BOT,
        1,
        f"{comments.marker('triage')}\nold\n{state}",
        association="NONE",
        database_id=99,
    )
    github = github_for()
    claude = FakeClaude({
        "complexity": "high",
        "rationale": "Now rewrites the event loop.",
    })
    runner(github, claude).triage(
        pull_request(
            labels=frozenset({"complexity: low", "status: waiting on maintainer"}),
            comments=(existing,),
            comment_count=1,
            additions=400,
        )
    )
    writes = github.writes()
    assert (
        "POST",
        f"{REPO}/issues/7/labels",
        {"labels": ["complexity: high"]},
    ) in writes
    assert ("DELETE", f"{REPO}/issues/7/labels/complexity%3A%20low", None) in writes
    (update,) = [w for w in writes if w[0] == "PATCH"]
    assert update[1] == f"{REPO}/issues/comments/99"
    assert comments.decode_state(update[2]["body"])["size"] == 402


def test_the_status_label_is_swapped():
    github = github_for()
    runner(github, None).triage(
        pull_request(labels=frozenset({"status: waiting on submitter"}))
    )
    writes = github.writes()
    assert (
        "POST",
        f"{REPO}/issues/7/labels",
        {"labels": ["status: waiting on maintainer"]},
    ) in writes
    assert (
        "DELETE",
        f"{REPO}/issues/7/labels/status%3A%20waiting%20on%20submitter",
        None,
    ) in writes


def test_the_estimate_budget_is_respected():
    github = github_for()
    claude = FakeClaude()
    runner(github, claude, estimates=0).triage(pull_request())
    assert claude.calls == []
    assert "**Complexity:** not estimated yet." in created_comment(github)


def test_claude_failures_are_reported_not_raised(capsys: pytest.CaptureFixture[str]):
    github = github_for()
    runner(github, FakeClaude(ClaudeError("Claude stopped with refusal"))).triage(
        pull_request()
    )
    assert (
        "::warning::#7: could not estimate complexity: Claude stopped with refusal"
        in capsys.readouterr().out
    )
    assert "not estimated yet" in created_comment(github)


def test_maintainer_comments_are_judged_once():
    note = comment(MAINTAINER, 3, "Could you add a test?", node_id="IC_ask")
    github = github_for()
    claude = FakeClaude({"verdicts": [{"id": "IC_ask", "asks_author": True}]}, ESTIMATE)
    verdict = runner(github, claude).triage(
        pull_request(comments=(note,), comment_count=1)
    )
    assert verdict.status is triage.Status.SUBMITTER
    body = created_comment(github)
    assert comments.decode_state(body)["judged"] == {"IC_ask": True}

    again = pull_request(
        comments=(note, comment(BOT, 4, body, association="NONE")),
        comment_count=2,
        labels=frozenset({"status: waiting on submitter", "complexity: medium"}),
    )
    claude = FakeClaude()
    assert runner(github_for(), claude).triage(again).status is triage.Status.SUBMITTER
    assert claude.calls == []


def test_the_comment_is_found_beyond_the_fetched_page():
    github = github_for()
    github.route(
        "GET",
        f"{REPO}/issues/7/comments",
        [
            {
                "node_id": "IC_old",
                "id": 5,
                "user": {"login": "github-actions[bot]", "type": "Bot"},
                "author_association": "NONE",
                "body": f"{comments.marker('triage')}\nold",
                "created_at": "2026-09-01T00:00:00Z",
            }
        ],
    )
    runner(github, None).triage(pull_request(comment_count=80))
    assert [w[:2] for w in github.writes() if w[0] == "PATCH"] == [
        ("PATCH", f"{REPO}/issues/comments/5")
    ]


def test_state_tolerates_garbage():
    state = triage.State.load(
        comments.encode_state({
            "complexity": "huge",
            "size": "big",
            "judged": ["x"],
            "rationale": "",
        })
    )
    assert state == triage.State()


def test_sweep_counts_failures(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    def fetch_open(github: Any) -> Iterator[PullRequest]:
        yield pull_request(number=7)
        yield pull_request(number=8)

    monkeypatch.setattr(pulls, "fetch_open", fetch_open)
    github = github_for()
    github.route("POST", f"{REPO}/issues/8/labels", GitHubError(500, "boom"))
    assert runner(github, None).sweep() == 1
    assert "::error::#8: GitHub API error 500: boom" in capsys.readouterr().out


def test_find_by_head_queries_the_fork_branch():
    github = FakeGitHub()
    urls = []

    def pulls_for(url: str, body: Any) -> list[dict[str, int]]:
        urls.append(url)
        return [{"number": 12}]

    github.route("GET", f"{REPO}/pulls", pulls_for)
    assert triage.find_by_head(github, "contributor", "fix/a&b") == [12]
    assert "head=contributor%3Afix%2Fa%26b" in urls[0]


def test_author_comments_are_not_judged():
    github = github_for()
    claude = FakeClaude(ESTIMATE)
    runner(github, claude).triage(
        pull_request(comments=(comment(AUTHOR, 2, "Done!", association="CONTRIBUTOR"),))
    )
    assert len(claude.calls) == 1  # only the estimate


def test_a_github_failure_while_estimating_still_labels_the_status(
    capsys: pytest.CaptureFixture[str],
):
    github = github_for()
    github.route("DIFF", f"{REPO}/pulls/7", GitHubError(502, "bad gateway"))
    runner(github, FakeClaude()).triage(pull_request())
    assert "could not estimate complexity" in capsys.readouterr().out
    assert (
        "POST",
        f"{REPO}/issues/7/labels",
        {"labels": ["status: waiting on maintainer"]},
    ) in github.writes()
