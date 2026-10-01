"""The bot's comments: one per purpose, edited in place, carrying their own state.

Each comment starts with a marker naming its purpose. Only comments that a bot
account wrote count as the bot's, so nobody can plant state by pasting a marker.
"""

from __future__ import annotations

import json
import re
import time
from collections.abc import Callable, Iterable, Mapping
from typing import Any

from scripts.pr_bot.github import GitHub
from scripts.pr_bot.pulls import Actor, Comment, parse_time

Writer = Callable[..., None]
# Linked from every comment, so readers can see how the bot decides.
README = "https://github.com/reflex-dev/reflex/blob/main/scripts/pr_bot/README.md"

_STATE = re.compile(r"<!-- reflex-pr-bot:state (\{.*?\}) -->", re.DOTALL)


def marker(purpose: str) -> str:
    """Return the marker that opens the bot's comment for one purpose.

    Args:
        purpose: ``triage``, ``overlap`` or ``on-deck``.

    Returns:
        An HTML comment, invisible in the rendered comment.
    """
    return f"<!-- reflex-pr-bot:{purpose} -->"


def encode_state(state: Mapping[str, Any]) -> str:
    """Embed state in a comment.

    Args:
        state: JSON-serializable state.

    Returns:
        An HTML comment holding the state. Angle brackets are escaped inside the
        JSON, so no value can end the HTML comment early.
    """
    payload = json.dumps(state, sort_keys=True, separators=(",", ":"))
    payload = payload.replace("<", "\\u003c").replace(">", "\\u003e")
    return f"<!-- reflex-pr-bot:state {payload} -->"


def decode_state(body: str) -> dict[str, Any]:
    """Read the state a comment carries.

    Args:
        body: The comment's Markdown.

    Returns:
        The state, or an empty dict when there is none or it is unreadable.
    """
    match = _STATE.search(body)
    if match is None:
        return {}
    try:
        state = json.loads(match.group(1))
    except ValueError:
        return {}
    return state if isinstance(state, dict) else {}


def sanitize(text: str, limit: int) -> str:
    """Make model-written text safe to put in a comment.

    Args:
        text: Text Claude wrote, possibly steered by a pull request's content.
        limit: The most characters to keep.

    Returns:
        One line of plain text that cannot open HTML, links or images, or mention
        anyone.
    """
    text = " ".join(text.split())
    if len(text) > limit:
        text = text[: limit - 1].rstrip() + "…"
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    text = text.replace("[", "\\[").replace("]", "\\]")
    return text.replace("@", "@&#8203;")


def code(names: Iterable[str], limit: int | None = None) -> str:
    """List names, such as paths or check names, as inline code.

    Args:
        names: The names; pull request content can choose them, so backticks are
            dropped rather than allowed to end the code span.
        limit: The most to name; the rest are counted.

    Returns:
        The names in backticks, separated by commas, then a count of the rest.
    """
    items = list(names)
    shown = items if limit is None else items[:limit]
    text = ", ".join(f"`{name.replace('`', '')}`" for name in shown)
    rest = len(items) - len(shown)
    return text + (f" and {rest} more" if rest else "")


def from_rest(entry: Mapping[str, Any]) -> Comment:
    """Turn an issue comment from the REST API into a comment.

    Args:
        entry: One item of the issue comments API.

    Returns:
        The comment.
    """
    user = entry.get("user") or {}
    return Comment(
        node_id=entry["node_id"],
        database_id=entry["id"],
        author=Actor(user.get("login", "ghost"), is_bot=user.get("type") == "Bot"),
        association=entry["author_association"],
        body=entry["body"] or "",
        created_at=parse_time(entry["created_at"]),
    )


def all_comments(github: GitHub, number: int) -> list[Comment]:
    """Fetch every comment on an issue or pull request.

    Args:
        github: The client.
        number: The issue or pull request number.

    Returns:
        The comments, oldest first.
    """
    return [
        from_rest(entry)
        for entry in github.paginate(github.repo_path(f"issues/{number}/comments"))
    ]


def find(comments: Iterable[Comment], purpose: str) -> list[Comment]:
    """Find the bot's comments for one purpose.

    Args:
        comments: Comments on a pull request.
        purpose: The purpose their marker names.

    Returns:
        The matching comments written by a bot account, oldest first.
    """
    tag = marker(purpose)
    return sorted(
        (c for c in comments if c.author.is_bot and c.body.startswith(tag)),
        key=lambda comment: comment.created_at,
    )


def writer(*, dry_run: bool, pause: float = 0.0) -> Writer:
    """Make the function every change to GitHub goes through.

    Args:
        dry_run: Skip the changes, so a run only reports what it would do.
        pause: Seconds to wait after each change, to stay under GitHub's secondary
            rate limit (80 content-creating requests a minute) in long runs.

    Returns:
        A function that calls ``action(*args)`` unless this is a dry run.
    """

    def write(action: Callable[..., Any], *args: Any) -> None:
        """Make one change.

        Args:
            action: The client method that makes it.
            *args: Its arguments.
        """
        if dry_run:
            return
        action(*args)
        if pause:
            time.sleep(pause)

    return write


def upsert(
    github: GitHub,
    number: int,
    body: str,
    existing: list[Comment],
    write: Writer,
    *,
    create: bool = True,
) -> str:
    """Make a pull request carry exactly one bot comment with this body.

    Args:
        github: The client.
        number: The pull request number.
        body: The comment's Markdown, starting with its marker.
        existing: The bot's comments for the same purpose, oldest first.
        write: Makes (or, in a dry run, skips) each change.
        create: Whether to post the comment when there is none to edit.

    Returns:
        What happened: ``created``, ``updated``, ``unchanged`` or ``skipped``.
    """
    if not existing:
        if not create:
            return "skipped"
        write(github.create_comment, number, body)
        return "created"
    keep, *duplicates = existing
    # Two runs racing on a new pull request can both post; keep the first.
    for duplicate in duplicates:
        write(github.delete_comment, duplicate.database_id)
    if keep.body.replace("\r\n", "\n") == body:
        return "updated" if duplicates else "unchanged"
    write(github.update_comment, keep.database_id, body)
    return "updated"
