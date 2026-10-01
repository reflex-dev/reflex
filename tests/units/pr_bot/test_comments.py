"""Unit tests for scripts/pr_bot/comments.py (the bot's own comments)."""

from __future__ import annotations

from typing import Any

import pytest

from scripts.pr_bot import comments
from tests.units.pr_bot.conftest import GREPTILE, MAINTAINER, FakeGitHub, comment

MARKER = comments.marker("triage")


def test_state_round_trips_through_a_comment():
    state = {"rationale": "Ends with --> and <!-- inside", "judged": {"IC_1": True}}
    embedded = comments.encode_state(state)
    # Nothing in the values can end the HTML comment early.
    assert embedded.count("-->") == 1
    assert embedded.endswith(" -->")
    assert comments.decode_state(f"text\n{embedded}\nmore") == state


@pytest.mark.parametrize(
    "body",
    [
        "no state here",
        "<!-- reflex-pr-bot:state {not json} -->",
        "<!-- reflex-pr-bot:state {}x -->",
    ],
)
def test_unreadable_state_is_empty(body: str):
    assert comments.decode_state(body) == {}


def test_sanitize_neutralizes_markup_and_mentions():
    text = "Ping @masenf <img src=x> [click](https://evil) &\n\n  done"
    assert comments.sanitize(text, 200) == (
        "Ping @&#8203;masenf &lt;img src=x&gt; \\[click\\](https://evil) &amp; done"
    )


def test_sanitize_truncates_before_escaping():
    assert comments.sanitize("a" * 10, 5) == "aaaa…"


def test_find_only_trusts_bot_comments_with_the_marker():
    ours = comment(GREPTILE, 2, f"{MARKER}\nnew", database_id=2)
    older = comment(GREPTILE, 1, f"{MARKER}\nold", database_id=1)
    planted = comment(MAINTAINER, 0, f"{MARKER}\nfake")
    quoted = comment(GREPTILE, 3, f"> {MARKER}")
    assert comments.find([ours, planted, quoted, older], "triage") == [older, ours]


def test_from_rest_reads_the_issue_comments_api():
    entry = {
        "node_id": "IC_x",
        "id": 9,
        "user": {"login": "github-actions[bot]", "type": "Bot"},
        "author_association": "NONE",
        "body": None,
        "created_at": "2026-09-01T00:00:00Z",
    }
    parsed = comments.from_rest(entry)
    assert parsed.author.is_bot
    assert parsed.body == ""
    assert parsed.database_id == 9


def recorder() -> tuple[list[tuple[str, tuple[Any, ...]]], comments.Writer]:
    """Make a writer that records the changes instead of making them.

    Returns:
        The recorded changes, and the writer.
    """
    calls: list[tuple[str, tuple[Any, ...]]] = []

    def write(action: Any, *args: Any) -> None:
        calls.append((action.__name__, args))

    return calls, write


def test_upsert_creates_when_missing():
    calls, write = recorder()
    assert comments.upsert(FakeGitHub(), 7, "body", [], write) == "created"
    assert calls == [("create_comment", (7, "body"))]


def test_upsert_skips_creation_when_told():
    calls, write = recorder()
    assert (
        comments.upsert(FakeGitHub(), 7, "body", [], write, create=False) == "skipped"
    )
    assert calls == []


def test_upsert_edits_in_place_and_drops_duplicates():
    calls, write = recorder()
    first = comment(GREPTILE, 1, "old", database_id=1)
    second = comment(GREPTILE, 2, "old", database_id=2)
    assert comments.upsert(FakeGitHub(), 7, "new", [first, second], write) == "updated"
    assert calls == [("delete_comment", (2,)), ("update_comment", (1, "new"))]


def test_upsert_leaves_an_identical_comment_alone():
    calls, write = recorder()
    existing = comment(GREPTILE, 1, "same\r\nbody")
    assert (
        comments.upsert(FakeGitHub(), 7, "same\nbody", [existing], write) == "unchanged"
    )
    assert calls == []


def test_writer_dry_run_changes_nothing():
    github = FakeGitHub()
    comments.writer(dry_run=True)(github.create_comment, 7, "body")
    assert github.requests == []


def test_writer_makes_the_change():
    github = FakeGitHub()
    github.route("POST", "repos/reflex-dev/reflex/issues/7/comments", {})
    comments.writer(dry_run=False)(github.create_comment, 7, "body")
    assert github.writes() == [
        ("POST", "repos/reflex-dev/reflex/issues/7/comments", {"body": "body"})
    ]


def test_all_comments_pages_through_rest():
    github = FakeGitHub()
    github.route(
        "GET",
        "repos/reflex-dev/reflex/issues/7/comments",
        [
            {
                "node_id": "IC_1",
                "id": 1,
                "user": {"login": "someone", "type": "User"},
                "author_association": "NONE",
                "body": "hi",
                "created_at": "2026-09-01T00:00:00Z",
            }
        ],
    )
    assert [c.body for c in comments.all_comments(github, 7)] == ["hi"]
