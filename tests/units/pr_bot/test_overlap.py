"""Unit tests for scripts/pr_bot/overlap.py (pull requests that collide)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from scripts.pr_bot import comments, overlap
from scripts.pr_bot.git import Git
from tests.units.pr_bot.conftest import FakeClaude, FakeGitHub, Upstream

REPO = "repos/reflex-dev/reflex"


def node(number: int, author: str, files: list[str], **changes: Any) -> dict[str, Any]:
    """Build a catalog node for an open pull request.

    Args:
        number: Its number.
        author: Its author's login.
        files: The files it changes.
        **changes: Fields to override.

    Returns:
        The node.
    """
    return {
        "number": number,
        "title": f"Pull request {number}",
        "body": "",
        "isDraft": False,
        "baseRefName": "main",
        "headRefName": f"branch-{number}",
        "author": {"login": author},
        "closingIssuesReferences": {"nodes": []},
        "files": {"totalCount": len(files), "nodes": [{"path": f} for f in files]},
        **changes,
    }


def edit(lines: dict[int, str]) -> str:
    """Write app.py with some of its lines changed.

    Args:
        lines: Line numbers to new contents.

    Returns:
        The file's contents.
    """
    return "".join(f"{lines.get(n, f'line {n}')}\n" for n in range(1, 21))


def setup(
    upstream: tuple[Upstream, str], tmp_path: Path, catalog: list[dict[str, Any]]
) -> tuple[FakeGitHub, Git]:
    """Open pull requests 1 to 7 upstream and fake GitHub's view of them.

    Args:
        upstream: The upstream repository and its first commit.
        tmp_path: The test's temporary directory.
        catalog: The open pull requests GitHub lists.

    Returns:
        The fake GitHub and the bot's checkout.
    """
    repo, base = upstream
    pulls = {
        1: repo.commit(base, {"app.py": edit({5: "five, one way"})}),
        2: repo.commit(base, {"app.py": edit({5: "five, another way"})}),
        3: repo.commit(base, {"app.py": edit({15: "fifteen"})}),
        4: repo.commit(base, {"README.md": "Better readme\n"}),
        5: repo.commit(base, {"app.py": edit({5: "five, same author"})}),
        7: repo.commit(base, {"app.py": edit({5: "five, linked"})}),
    }
    for number, commit in pulls.items():
        repo.open_pull(number, commit)
    # main moved on since the branches were cut, without conflicting with them.
    repo.set_ref("refs/heads/main", repo.commit(base, {"other.py": "x = 1\n"}))
    github = FakeGitHub()
    github.graphql_handler = lambda query, variables: {
        "repository": {
            "pullRequests": {
                "nodes": catalog,
                "pageInfo": {"hasNextPage": False, "endCursor": None},
            }
        }
    }
    github.route(
        "GET",
        f"{REPO}/pulls/1/files",
        [{"filename": "app.py", "status": "modified", "additions": 1, "deletions": 1}],
    )
    github.route(
        "DIFF",
        f"{REPO}/pulls/1",
        "diff --git a/app.py b/app.py\n-line 5\n+five, one way\n",
    )
    github.route("GET", f"{REPO}/issues/1/comments", [])
    return github, Git(repo.clone(tmp_path / "checkout"))


CATALOG = [
    node(
        1,
        "alice",
        ["app.py"],
        body="Fixes #100. Alternative to #7.",
        closingIssuesReferences={"nodes": [{"number": 100}]},
    ),
    node(2, "bob", ["app.py"]),
    node(3, "carol", ["app.py"]),
    node(
        4,
        "dave",
        ["README.md"],
        body="Closes https://github.com/reflex-dev/reflex/issues/100",
    ),
    node(5, "Alice", ["app.py"]),
    node(6, "erin", ["app.py"], baseRefName="r/pre-1.0"),
    node(7, "frank", ["app.py"]),
]


def test_references_finds_numbers_and_urls():
    text = (
        "Fixes #12, see github.com/reflex-dev/reflex/pull/34, not owner/repo#56, "
        "an anchor page#7 or an entity &#8203;"
    )
    assert overlap.references(text, "reflex-dev/reflex") == {12, 34}


def test_find_overlaps(upstream: tuple[Upstream, str], tmp_path: Path):
    github, git = setup(upstream, tmp_path, CATALOG)
    claude = FakeClaude({
        "overlaps": [
            {
                "number": 4,
                "relation": "alternative",
                "explanation": "Both fix the readme.",
            },
            {
                "number": 999,
                "relation": "duplicate",
                "explanation": "Not shown to Claude.",
            },
            {"number": 3, "relation": "bogus", "explanation": "Not a relation."},
        ]
    })
    found, note = overlap.find_overlaps(github, claude, git, 1)
    assert note is None
    assert [(o.pull.number, o.relation, o.conflicts, o.issues) for o in found] == [
        (4, "alternative", [], [100]),
        (2, None, ["app.py"], []),
    ]
    # The comparison saw neither the author's own pull request, another base
    # branch, nor the pull request the new one already links to.
    prompt = claude.calls[0]["prompt"]
    assert "#2: Pull request 2" in prompt
    assert "#5" not in prompt
    assert "#6" not in prompt
    assert "#7:" not in prompt


def test_a_pull_request_that_conflicts_with_main_is_not_simulated(
    upstream: tuple[Upstream, str], tmp_path: Path
):
    github, git = setup(upstream, tmp_path, CATALOG)
    repo, _ = upstream
    main = git.out("ls-remote", "origin", "refs/heads/main").split()[0]
    repo.set_ref(
        "refs/heads/main", repo.commit(main, {"app.py": edit({5: "five on main"})})
    )
    found, note = overlap.find_overlaps(github, None, git, 1)
    assert note is not None
    assert "conflicts with `main`" in note
    assert [o.pull.number for o in found] == [4]


def test_render_lists_each_overlap():
    pull = overlap.OpenPull(
        7,
        "Fix @admin's <bug>",
        "",
        "bob",
        False,
        "main",
        "b",
        frozenset(),
        frozenset(),
        0,
    )
    body = overlap.render(
        [
            overlap.Overlap(
                pull,
                conflicts=["a.py"],
                relation="duplicate",
                explanation="Same fix.",
                issues=[3],
            ),
            overlap.Overlap(pull, shared=["b.py"], issues=[4]),
        ],
        None,
    )
    assert body.startswith(comments.marker("overlap"))
    assert "- #7: Fix @&#8203;admin's &lt;bug&gt; (by bob)" in body
    assert "  - Looks like a duplicate: Same fix." in body
    assert "  - Conflicts with this pull request in `a.py`." in body
    assert "  - Also changes `b.py`." in body
    assert "  - Both reference #3." in body


def test_run_comments_only_when_something_is_found(
    upstream: tuple[Upstream, str], tmp_path: Path
):
    github, git = setup(upstream, tmp_path, [CATALOG[0], CATALOG[2]])
    overlap.run(github, None, git, 1, comments.writer(dry_run=False))
    assert github.writes() == []


def test_run_corrects_an_earlier_comment(
    upstream: tuple[Upstream, str], tmp_path: Path
):
    github, git = setup(upstream, tmp_path, [CATALOG[0], CATALOG[2]])
    github.route(
        "GET",
        f"{REPO}/issues/1/comments",
        [
            {
                "node_id": "IC_1",
                "id": 3,
                "user": {"login": "github-actions[bot]", "type": "Bot"},
                "author_association": "NONE",
                "body": f"{comments.marker('overlap')}\nold findings",
                "created_at": "2026-09-01T00:00:00Z",
            }
        ],
    )
    overlap.run(github, None, git, 1, comments.writer(dry_run=False))
    ((method, path, body),) = github.writes()
    assert (method, path) == ("PATCH", f"{REPO}/issues/comments/3")
    assert "No overlap with other open pull requests found" in body["body"]


def test_run_posts_new_findings(upstream: tuple[Upstream, str], tmp_path: Path):
    github, git = setup(upstream, tmp_path, CATALOG)
    overlap.run(github, None, git, 1, comments.writer(dry_run=False))
    ((method, path, body),) = github.writes()
    assert (method, path) == ("POST", f"{REPO}/issues/1/comments")
    assert "- #2: Pull request 2 (by bob)" in body["body"]
    assert "- #4: Pull request 4 (by dave)" in body["body"]


def test_a_closed_pull_request_has_nothing_to_report(
    upstream: tuple[Upstream, str], tmp_path: Path
):
    github, git = setup(upstream, tmp_path, CATALOG[1:])
    assert overlap.find_overlaps(github, None, git, 1) == ([], None)
