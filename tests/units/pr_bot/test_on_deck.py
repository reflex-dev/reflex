"""Unit tests for scripts/pr_bot/on_deck.py (resolving conflicts on on-deck pull requests).

Each test builds a small upstream repository that stands in for GitHub: branches
plus the refs/pull/N/head refs GitHub publishes for pull requests.
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path
from typing import Any

import pytest

from scripts.pr_bot import comments, on_deck
from scripts.pr_bot.git import Git
from tests.units.pr_bot.conftest import FakeGitHub, Upstream, git

REPO = "repos/reflex-dev/reflex"
PR_LINE = "five, as the pull request has it"
MAIN_LINE = "five, as main has it"
RESOLVED = "five, combining both"


def lines(changes: dict[int, str]) -> str:
    """Write app.py with some of its lines changed.

    Args:
        changes: Line numbers to new contents.

    Returns:
        The file's contents.
    """
    return "".join(f"{changes.get(n, f'line {n}')}\n" for n in range(1, 21))


@dataclasses.dataclass
class Scenario:
    """A conflicting on-deck pull request and everything the jobs need to handle it."""

    upstream: Upstream
    github: FakeGitHub
    checkout: Git
    head: str
    base: str
    tmp: Path

    def candidate(self, **changes: Any) -> on_deck.Candidate:
        """Describe pull request 7 as the find job would.

        Args:
            **changes: Fields to override.

        Returns:
            The candidate.
        """
        fields = {
            "number": 7,
            "head_sha": self.head,
            "base_ref": "main",
            "base_sha": self.base,
            "head_repository": "contributor/reflex",
            "head_ref": "fix-thing",
            "pushable": True,
            **changes,
        }
        return on_deck.Candidate(**fields)


def pull(head_sha: str, **changes: Any) -> dict[str, Any]:
    """Build the REST pull request the push job reads.

    Args:
        head_sha: The pull request's head commit.
        **changes: Fields to override.

    Returns:
        The pull request JSON.
    """
    return {
        "state": "open",
        "labels": [{"name": "on deck"}],
        "title": "Fix the thing",
        "body": "Make line five better.",
        "maintainer_can_modify": True,
        "head": {
            "sha": head_sha,
            "ref": "fix-thing",
            "repo": {"full_name": "contributor/reflex"},
        },
        "base": {"ref": "main"},
        **changes,
    }


def on_deck_node(number: int, **changes: Any) -> dict[str, Any]:
    """Build a node of the on-deck query.

    Args:
        number: The pull request number.
        **changes: Fields to override.

    Returns:
        The node.
    """
    return {
        "number": number,
        "headRefName": f"branch-{number}",
        "baseRefName": "main",
        "isCrossRepository": True,
        "maintainerCanModify": True,
        "headRepository": {"nameWithOwner": "contributor/reflex"},
        **changes,
    }


@pytest.fixture
def scenario(upstream: tuple[Upstream, str], tmp_path: Path) -> Scenario:
    """Open pull request 7, which conflicts with main on line five, and 8, which does not.

    Args:
        upstream: The upstream repository and its first commit.
        tmp_path: The test's temporary directory.

    Returns:
        The scenario.
    """
    repo, start = upstream
    head = repo.commit(start, {"app.py": lines({5: PR_LINE}), "docs.md": "New docs\n"})
    repo.open_pull(7, head)
    repo.open_pull(8, repo.commit(start, {"README.md": "Better readme\n"}))
    repo.open_pull(9, head)
    base = repo.commit(
        start, {"app.py": lines({5: MAIN_LINE, 18: "eighteen"}), "main.py": "x = 1\n"}
    )
    repo.set_ref("refs/heads/main", base)
    github = FakeGitHub()
    github.graphql_handler = lambda query, variables: {
        "repository": {
            "defaultBranchRef": {"name": "main"},
            "pullRequests": {
                "nodes": [
                    on_deck_node(7),
                    on_deck_node(8),
                    on_deck_node(9, baseRefName="r/pre-1.0"),
                ]
            },
        }
    }
    github.route("GET", f"{REPO}/pulls/7", pull(head))
    github.route("GET", f"{REPO}/issues/7/comments", [])
    github.route("GET", "users/reflex-pr-bot[bot]", {"id": 123})
    return Scenario(
        repo, github, Git(repo.clone(tmp_path / "bot")), head, base, tmp_path
    )


def bot_comment(body: str) -> dict[str, Any]:
    """Build a comment the bot left, as the REST API returns it.

    Args:
        body: The comment's text.

    Returns:
        The comment JSON.
    """
    return {
        "node_id": "IC_1",
        "id": 41,
        "user": {"login": "reflex-pr-bot[bot]", "type": "Bot"},
        "author_association": "NONE",
        "body": body,
        "created_at": "2026-09-01T00:00:00Z",
    }


def prepare(scenario: Scenario, **changes: Any) -> str:
    """Run the prepare step for pull request 7.

    Args:
        scenario: The scenario.
        **changes: Candidate fields to override.

    Returns:
        What prepare found.
    """
    return on_deck.prepare(
        scenario.github,
        scenario.checkout,
        candidate=scenario.candidate(**changes),
        worktree=scenario.tmp / "work",
        context=scenario.tmp / "context",
        out=scenario.tmp / "out",
    )


def agent_says(scenario: Scenario, **report: Any) -> Path:
    """Write the result Claude Code reports.

    Args:
        scenario: The scenario.
        **report: Report fields to override.

    Returns:
        The result file.
    """
    output = scenario.tmp / "claude.json"
    structured = {
        "resolved": True,
        "summary": "Kept both versions of line five.",
        "files": [{"path": "app.py", "resolution": "Combined both edits."}],
        **report,
    }
    output.write_text(
        json.dumps({
            "type": "result",
            "subtype": "success",
            "is_error": False,
            "structured_output": structured,
        })
    )
    return output


def resolve(scenario: Scenario) -> None:
    """Do what Claude would: rewrite the conflicted file without markers.

    Args:
        scenario: The scenario, with the merge prepared.
    """
    (scenario.tmp / "work" / "app.py").write_text(lines({5: RESOLVED, 18: "eighteen"}))


def finalize(scenario: Scenario, agent_output: Path) -> dict[str, Any]:
    """Run the finalize step for pull request 7.

    Args:
        scenario: The scenario.
        agent_output: The result Claude Code reported.

    Returns:
        The result.
    """
    return on_deck.finalize(
        candidate=scenario.candidate(),
        worktree=scenario.tmp / "work",
        context=scenario.tmp / "context",
        agent_output=agent_output,
        out=scenario.tmp / "out",
    )


def test_find_lists_conflicting_pull_requests_into_the_default_branch(
    scenario: Scenario,
):
    assert on_deck.find(scenario.github, scenario.checkout) == [
        scenario.candidate(head_ref="branch-7")
    ]


def test_find_lets_a_failure_rest_until_the_branch_changes(scenario: Scenario):
    state = comments.encode_state({"failed_head": scenario.head})
    scenario.github.route(
        "GET",
        f"{REPO}/issues/7/comments",
        [bot_comment(f"{comments.marker('on-deck')}\n{state}")],
    )
    assert on_deck.find(scenario.github, scenario.checkout) == []
    assert [
        c.number for c in on_deck.find(scenario.github, scenario.checkout, forced=7)
    ] == [7]


def test_find_marks_forks_without_maintainer_edits_unpushable(scenario: Scenario):
    scenario.github.graphql_handler = lambda query, variables: {
        "repository": {
            "defaultBranchRef": {"name": "main"},
            "pullRequests": {"nodes": [on_deck_node(7, maintainerCanModify=False)]},
        }
    }
    (candidate,) = on_deck.find(scenario.github, scenario.checkout)
    assert not candidate.pushable


def test_prepare_writes_what_claude_needs(scenario: Scenario):
    assert prepare(scenario) == "conflicted"
    context = scenario.tmp / "context"
    assert json.loads((context / "conflicted.json").read_text()) == ["app.py"]
    prompt = (context / "prompt.md").read_text()
    assert "pull request #7" in prompt
    assert "\n- app.py\n" in prompt
    assert str(context) in prompt
    assert json.loads((context / "schema.json").read_text()) == on_deck.REPORT_SCHEMA
    assert "Make line five better." in (context / "pull-request.md").read_text()
    sides = (context / "01-app.py.md").read_text()
    assert f"+{PR_LINE}" in sides
    assert f"+{MAIN_LINE}" in sides
    work = (scenario.tmp / "work" / "app.py").read_text()
    # zdiff3 shows the common ancestor too.
    assert "||||||| " in work
    assert on_deck.has_markers(work)


def test_prepare_notices_a_moved_pull_request(scenario: Scenario):
    assert prepare(scenario, head_sha="0" * 40) == "moved"
    assert (
        json.loads((scenario.tmp / "out" / "result.json").read_text())["status"]
        == "moved"
    )


def test_prepare_notices_a_clean_merge(scenario: Scenario):
    head = git(scenario.upstream.path, "rev-parse", "refs/pull/8/head")
    assert prepare(scenario, number=8, head_sha=head) == "clean"


def test_prepare_refuses_conflicts_that_need_more_than_edits(
    upstream: tuple[Upstream, str], tmp_path: Path
):
    repo, start = upstream
    head = repo.commit(start, {"app.py": None})
    repo.open_pull(7, head)
    base = repo.commit(start, {"app.py": lines({5: MAIN_LINE})})
    repo.set_ref("refs/heads/main", base)
    github = FakeGitHub()
    scenario = Scenario(
        repo, github, Git(repo.clone(tmp_path / "bot")), head, base, tmp_path
    )
    assert prepare(scenario) == "unsupported"
    result = json.loads((tmp_path / "out" / "result.json").read_text())
    assert result["conflicted"] == ["app.py"]
    assert "can't be resolved by editing text" in result["reason"]


def test_finalize_bundles_only_the_resolved_files(scenario: Scenario):
    prepare(scenario)
    resolve(scenario)
    # Edits outside the conflicted files never reach the merge.
    (scenario.tmp / "work" / "README.md").write_text("Sneaky edit\n")
    result = finalize(scenario, agent_says(scenario))
    assert result["status"] == "resolved"
    assert result["files"] == [{"path": "app.py", "resolution": "Combined both edits."}]
    tree, conflicted = on_deck.verify(
        scenario.checkout,
        scenario.tmp / "out" / "merge.bundle",
        scenario.head,
        scenario.base,
    )
    assert conflicted == ["app.py"]
    show = scenario.checkout.out
    assert (
        show("cat-file", "-p", f"{tree}:app.py")
        == lines({5: RESOLVED, 18: "eighteen"}).strip()
    )
    assert show("cat-file", "-p", f"{tree}:README.md") == "Readme"
    assert show("cat-file", "-p", f"{tree}:docs.md") == "New docs"
    assert show("cat-file", "-p", f"{tree}:main.py") == "x = 1"


@pytest.mark.parametrize(
    ("report", "expected"),
    [
        (
            {"resolved": False, "summary": "The two sides disagree on the API."},
            "Claude did not resolve every conflict: The two sides disagree on the API.",
        ),
        ({}, "conflict markers remain in `app.py`"),
    ],
)
def test_finalize_rejects_unfinished_work(
    scenario: Scenario, report: dict[str, Any], expected: str
):
    prepare(scenario)
    result = finalize(scenario, agent_says(scenario, **report))
    assert result["status"] == "failed"
    assert result["reason"] == expected
    assert not (scenario.tmp / "out" / "merge.bundle").exists()


@pytest.mark.parametrize(
    ("output", "expected"),
    [
        (None, "Claude Code produced no result."),
        (
            {"type": "result", "subtype": "error_max_turns", "is_error": True},
            "Claude Code stopped early (error_max_turns).",
        ),
        # What Claude Code 2.1.285 writes when the API rejects the key.
        (
            {
                "type": "result",
                "subtype": "success",
                "is_error": True,
                "terminal_reason": "api_error",
                "api_error_status": 401,
                "result": "Authentication error",
            },
            "Claude Code stopped early (api_error, 401).",
        ),
    ],
)
def test_finalize_reports_a_failed_agent(
    scenario: Scenario, output: dict[str, Any] | None, expected: str
):
    prepare(scenario)
    resolve(scenario)
    agent_output = scenario.tmp / "claude.json"
    if output is not None:
        agent_output.write_text(json.dumps(output))
    result = finalize(scenario, agent_output)
    assert (result["status"], result["reason"]) == ("failed", expected)


def tampered_bundle(
    scenario: Scenario, files: dict[str, str], parents: list[str]
) -> Path:
    """Bundle a merge commit that differs from the fair resolution.

    Args:
        scenario: The scenario, with the merge prepared and resolved.
        files: Extra file changes to sneak in.
        parents: The commit's parents.

    Returns:
        The bundle.
    """
    work = Git(scenario.tmp / "work")
    for name, content in files.items():
        (scenario.tmp / "work" / name).write_text(content)
    work.run("add", "-A")
    commit = work.commit_tree(work.out("write-tree"), parents, "tampered")
    work.run("update-ref", "refs/heads/pr-bot-merge", commit)
    bundle = scenario.tmp / "tampered.bundle"
    work.run(
        "bundle",
        "create",
        str(bundle),
        "refs/heads/pr-bot-merge",
        f"^{scenario.head}",
        f"^{scenario.base}",
    )
    return bundle


def test_verify_rejects_changes_outside_the_conflicts(scenario: Scenario):
    prepare(scenario)
    resolve(scenario)
    bundle = tampered_bundle(
        scenario, {"README.md": "Sneaky edit\n"}, [scenario.head, scenario.base]
    )
    with pytest.raises(on_deck.VerificationError, match=r"no conflict: README\.md"):
        on_deck.verify(scenario.checkout, bundle, scenario.head, scenario.base)


def test_verify_rejects_other_parents(scenario: Scenario):
    prepare(scenario)
    resolve(scenario)
    bundle = tampered_bundle(scenario, {}, [scenario.head])
    with pytest.raises(on_deck.VerificationError, match="parents"):
        on_deck.verify(scenario.checkout, bundle, scenario.head, scenario.base)


def test_verify_rejects_leftover_markers(scenario: Scenario):
    prepare(scenario)
    resolve(scenario)
    bundle = tampered_bundle(
        scenario,
        {"app.py": "<<<<<<< HEAD\nx\n=======\ny\n>>>>>>> main\n"},
        [scenario.head, scenario.base],
    )
    with pytest.raises(on_deck.VerificationError, match="conflict markers"):
        on_deck.verify(scenario.checkout, bundle, scenario.head, scenario.base)


@pytest.fixture
def pushes(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, str]]:
    """Record pushes instead of making them.

    Args:
        monkeypatch: The monkeypatch fixture.

    Returns:
        The remotes and refspecs pushed.
    """
    sent: list[tuple[str, str]] = []
    monkeypatch.setattr(
        on_deck,
        "_push",
        lambda git, remote, refspec, token: sent.append((remote, refspec)),
    )
    return sent


def push(scenario: Scenario, artifact: Path | None = None) -> str:
    """Run the push step for pull request 7 from a fresh checkout.

    Args:
        scenario: The scenario.
        artifact: The resolve job's output directory.

    Returns:
        What happened.
    """
    return on_deck.push(
        scenario.github,
        Git(scenario.upstream.clone(scenario.tmp / "push-checkout")),
        number=7,
        artifact=artifact or scenario.tmp / "out",
        token="app-token",
        app_slug="reflex-pr-bot",
        write=comments.writer(dry_run=False),
    )


def test_push_sends_the_merge_as_the_app(
    scenario: Scenario, pushes: list[tuple[str, str]]
):
    prepare(scenario)
    resolve(scenario)
    finalize(scenario, agent_says(scenario))
    outcome = push(scenario)
    ((remote, refspec),) = pushes
    merge = refspec.split(":")[0]
    assert outcome == f"pushed {merge[:10]}"
    assert remote == "https://github.com/contributor/reflex.git"
    assert refspec.endswith(":refs/heads/fix-thing")
    checkout = Git(scenario.tmp / "push-checkout")
    assert checkout.out("rev-list", "--parents", "-n", "1", merge).split()[1:] == [
        scenario.head,
        scenario.base,
    ]
    assert checkout.out("log", "-1", "--format=%an <%ae>", merge) == (
        "reflex-pr-bot[bot] <123+reflex-pr-bot[bot]@users.noreply.github.com>"
    )
    ((method, path, body),) = scenario.github.writes()
    assert (method, path) == ("POST", f"{REPO}/issues/7/comments")
    assert "**Merged `main` into this branch**" in body["body"]
    assert "- `app.py`: Combined both edits." in body["body"]
    assert comments.decode_state(body["body"]) == {}


def test_push_explains_a_failed_resolution(
    scenario: Scenario, pushes: list[tuple[str, str]]
):
    prepare(scenario)
    finalize(
        scenario, agent_says(scenario, resolved=False, summary="Incompatible @designs.")
    )
    push(scenario)
    assert pushes == []
    ((_, _, body),) = scenario.github.writes()
    assert (
        "could not resolve them: Claude did not resolve every conflict: Incompatible @&#8203;designs."
        in body["body"]
    )
    assert "resolve the conflicts in `app.py`" in body["body"]
    assert comments.decode_state(body["body"]) == {"failed_head": scenario.head}


def test_push_explains_when_it_cannot_push(
    scenario: Scenario, pushes: list[tuple[str, str]]
):
    scenario.github.route(
        "GET", f"{REPO}/pulls/7", pull(scenario.head, maintainer_can_modify=False)
    )
    push(scenario, artifact=scenario.tmp / "missing")
    assert pushes == []
    ((_, _, body),) = scenario.github.writes()
    assert "can't push to its branch" in body["body"]


def test_push_reports_a_missing_result(
    scenario: Scenario, pushes: list[tuple[str, str]]
):
    push(scenario, artifact=scenario.tmp / "missing")
    ((_, _, body),) = scenario.github.writes()
    assert "the resolve job produced no result" in body["body"]


def test_push_rejects_a_tampered_bundle(
    scenario: Scenario, pushes: list[tuple[str, str]]
):
    prepare(scenario)
    resolve(scenario)
    finalize(scenario, agent_says(scenario))
    tampered = tampered_bundle(
        scenario, {"README.md": "Sneaky edit\n"}, [scenario.head, scenario.base]
    )
    (scenario.tmp / "out" / "merge.bundle").write_bytes(tampered.read_bytes())
    push(scenario)
    assert pushes == []
    ((_, _, body),) = scenario.github.writes()
    assert "rejected its own resolution" in body["body"]


@pytest.mark.parametrize(
    ("change", "expected"),
    [
        ({"labels": []}, "skipped: no longer an open on-deck pull request"),
        ({"state": "closed"}, "skipped: no longer an open on-deck pull request"),
        (
            {
                "head": {
                    "sha": "0" * 40,
                    "ref": "fix-thing",
                    "repo": {"full_name": "contributor/reflex"},
                }
            },
            "skipped: the pull request changed after the merge was prepared",
        ),
    ],
)
def test_push_stands_down(
    scenario: Scenario,
    pushes: list[tuple[str, str]],
    change: dict[str, Any],
    expected: str,
):
    prepare(scenario)
    resolve(scenario)
    finalize(scenario, agent_says(scenario))
    scenario.github.route("GET", f"{REPO}/pulls/7", pull(scenario.head, **change))
    assert push(scenario) == expected
    assert pushes == []
    assert scenario.github.writes() == []


def test_push_dry_run_changes_nothing(
    scenario: Scenario, pushes: list[tuple[str, str]]
):
    prepare(scenario)
    resolve(scenario)
    finalize(scenario, agent_says(scenario))
    on_deck.push(
        scenario.github,
        Git(scenario.upstream.clone(scenario.tmp / "push-checkout")),
        number=7,
        artifact=scenario.tmp / "out",
        token="app-token",
        app_slug="reflex-pr-bot",
        write=comments.writer(dry_run=True),
    )
    assert pushes == []
    assert scenario.github.writes() == []


def test_a_rejected_push_is_reported_and_not_retried(
    scenario: Scenario, monkeypatch: pytest.MonkeyPatch
):
    prepare(scenario)
    resolve(scenario)
    finalize(scenario, agent_says(scenario))

    def refuse(git: Git, remote: str, refspec: str, token: str) -> None:
        """Reject the push the way GitHub would.

        Args:
            git: The checkout.
            remote: The repository URL.
            refspec: What to push.
            token: The token.

        Raises:
            GitError: Always.
        """
        msg = "remote: Permission denied"
        raise on_deck.GitError(msg)

    monkeypatch.setattr(on_deck, "_push", refuse)
    assert push(scenario) == "failed: the push was rejected"
    ((_, _, body),) = scenario.github.writes()
    assert "GitHub rejected its push" in body["body"]
    assert comments.decode_state(body["body"]) == {"failed_head": scenario.head}
