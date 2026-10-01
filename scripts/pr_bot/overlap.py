"""Find the open pull requests a new one collides with.

Three signals, from cheapest to most judgment:

- conflicts: both pull requests are merged onto the base branch in memory, then
  into each other, so a conflict is between the two changes and not with drift on
  the base branch;
- linked issues: both close or reference the same issue;
- purpose: Claude compares the new pull request with every open one and names the
  duplicates, alternative fixes, and changes that interact.

Shared files alone are not reported: two unrelated fixes in ``state.py`` are
routine. Pull requests by the same author are skipped (a stack of pull requests
overlaps by design), and so are the ones the new pull request already links to.
"""

from __future__ import annotations

import dataclasses
import re
from datetime import datetime, timezone
from typing import Any

import anthropic

from scripts.pr_bot import comments, diffs
from scripts.pr_bot.git import Git
from scripts.pr_bot.github import GitHub
from scripts.pr_bot.llm import Claude, ClaudeError, fence
from scripts.pr_bot.pulls import same_login

PURPOSE = "overlap"
RELATIONS = ("duplicate", "alternative", "overlapping")
_RELATION_TEXT = {
    "duplicate": "Looks like a duplicate",
    "alternative": "Solves the same problem differently",
    "overlapping": "Changes interact",
}
# Room for the new pull request's diff and for each other pull request's
# description in the comparison prompt.
_DIFF_BUDGET = 40_000
_DESCRIPTION_LIMIT = 6_000
_SUMMARY_LIMIT = 500
_MAX_REPORTED = 10

_CATALOG = """
query($owner: String!, $name: String!, $after: String) {
  repository(owner: $owner, name: $name) {
    pullRequests(
      states: OPEN, first: 50, after: $after,
      orderBy: {field: CREATED_AT, direction: DESC}
    ) {
      pageInfo { hasNextPage endCursor }
      nodes {
        number title body isDraft baseRefName headRefName
        author { login }
        closingIssuesReferences(first: 10) { nodes { number } }
        files(first: 100) { totalCount nodes { path } }
      }
    }
  }
}
"""

COMPARE_SYSTEM = """\
You help the maintainers of Reflex, a Python web framework, notice when a new pull \
request overlaps with other open pull requests. Compare the new pull request with \
each of the others and report only real overlaps:
- duplicate: both make essentially the same change or fix the same bug the same \
way, so one of them should probably be closed.
- alternative: both address the same problem or issue in different ways, so the \
maintainers should choose between them.
- overlapping: they change the same behavior or code path in ways that interact, \
such as one refactoring what the other extends, so they need coordinating or a \
deliberate merge order.
Working in the same area of the code, or touching the same files for unrelated \
reasons, is not an overlap. Most new pull requests overlap with none of the others; \
answer with an empty list then. Keep each explanation to one sentence a maintainer \
can verify."""

_COMPARE_SCHEMA = {
    "type": "object",
    "properties": {
        "overlaps": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "number": {"type": "integer"},
                    "relation": {"type": "string", "enum": list(RELATIONS)},
                    "explanation": {"type": "string"},
                },
                "required": ["number", "relation", "explanation"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["overlaps"],
    "additionalProperties": False,
}


@dataclasses.dataclass(frozen=True)
class OpenPull:
    """An open pull request, as the comparison sees it."""

    number: int
    title: str
    body: str
    author: str
    is_draft: bool
    base_ref: str
    head_ref: str
    issues: frozenset[int]
    files: frozenset[str]
    file_count: int


@dataclasses.dataclass
class Overlap:
    """What links another pull request to the new one."""

    pull: OpenPull
    conflicts: list[str] = dataclasses.field(default_factory=list)
    shared: list[str] = dataclasses.field(default_factory=list)
    issues: list[int] = dataclasses.field(default_factory=list)
    relation: str | None = None
    explanation: str = ""

    @property
    def strong(self) -> bool:
        """Whether this is worth telling anyone about."""
        return bool(self.conflicts or self.issues or self.relation)

    @property
    def rank(self) -> int:
        """How urgent it is: duplicates first, interacting changes last."""
        weights = {"duplicate": 8, "alternative": 4, "overlapping": 1}
        return (
            weights.get(self.relation or "", 0)
            + 2 * bool(self.conflicts)
            + 2 * bool(self.issues)
        )


def fetch_catalog(github: GitHub) -> list[OpenPull]:
    """Fetch every open pull request.

    Args:
        github: The client.

    Returns:
        The pull requests, newest first.
    """
    return [
        OpenPull(
            number=node["number"],
            title=node["title"],
            body=node["body"] or "",
            author=(node["author"] or {"login": "ghost"})["login"],
            is_draft=node["isDraft"],
            base_ref=node["baseRefName"],
            head_ref=node["headRefName"],
            issues=frozenset(
                issue["number"] for issue in node["closingIssuesReferences"]["nodes"]
            ),
            files=frozenset(file["path"] for file in node["files"]["nodes"]),
            file_count=node["files"]["totalCount"],
        )
        for node in github.graphql_nodes(
            _CATALOG,
            "repository",
            "pullRequests",
            owner=github.owner,
            name=github.name,
        )
    ]


def references(text: str, repository: str) -> set[int]:
    """Find the issue and pull request numbers a description refers to.

    Args:
        text: A title or description.
        repository: The repository as ``owner/name``, for full URLs.

    Returns:
        The numbers referenced as ``#123`` or by URL.
    """
    pattern = re.compile(
        r"(?:(?<![\w/&#])#|github\.com/"
        + re.escape(repository)
        + r"/(?:issues|pull)/)(\d+)\b"
    )
    return {int(match) for match in pattern.findall(text)}


def simulate_conflicts(
    git: Git, base_ref: str, number: int, others: list[int]
) -> tuple[dict[int, list[str]], str | None]:
    """Find which pull requests conflict with this one once both are merged.

    Each pull request is first merged onto the current base branch in memory, so a
    conflict found between the two merges is between the two changes themselves.

    Args:
        git: The repository, with full history of the base branch.
        base_ref: The base branch both pull requests target.
        number: The new pull request.
        others: The pull requests to check against it.

    Returns:
        The conflicting hand-written files per pull request, and a note when the
        check could not run because the new pull request conflicts with its base.
    """
    git.run(
        "fetch",
        "--no-tags",
        "--quiet",
        "origin",
        f"+refs/heads/{base_ref}:refs/pr-bot/base",
        *(f"+refs/pull/{n}/head:refs/pr-bot/pull/{n}" for n in [number, *others]),
    )
    base = git.out("rev-parse", "refs/pr-bot/base")
    mine = git.merged(base, f"refs/pr-bot/pull/{number}")
    if mine is None:
        return {}, (
            f"This pull request conflicts with `{base_ref}`, so it was not checked "
            "for conflicts with other pull requests."
        )
    found = {}
    for other in others:
        theirs = git.merged(base, f"refs/pr-bot/pull/{other}")
        if theirs is None:
            continue
        _, conflicts = git.merge_tree(mine, theirs)
        conflicts = [path for path in conflicts if not diffs.is_generated(path)]
        if conflicts:
            found[other] = conflicts
    return found, None


def _summary(pull: OpenPull) -> str:
    """Describe another open pull request for the comparison prompt.

    Args:
        pull: The pull request.

    Returns:
        Its title, author, linked issues, files and the start of its description.
    """
    files = sorted(pull.files)
    shown = ", ".join(files[:20])
    if pull.file_count > 20:
        shown += f", and {pull.file_count - 20} more"
    issues = ", ".join(f"#{n}" for n in sorted(pull.issues)) or "none"
    body = pull.body[:_SUMMARY_LIMIT] + (
        "..." if len(pull.body) > _SUMMARY_LIMIT else ""
    )
    draft = " (draft)" if pull.is_draft else ""
    return (
        f"#{pull.number}{draft}: {pull.title}\n"
        f"Author: {pull.author}; branch: {pull.head_ref}; closes: {issues}\n"
        f"Files: {shown}\n"
        f"Description: {body or '(none)'}"
    )


def compare(
    claude: Claude,
    pull: OpenPull,
    files: list[dict[str, Any]],
    diff: str | None,
    others: list[OpenPull],
) -> list[dict[str, Any]]:
    """Have Claude find the pull requests that overlap with this one in purpose.

    Args:
        claude: The client.
        pull: The new pull request.
        files: Its entries of the pulls files API.
        diff: Its unified diff, or None when GitHub would not render it.
        others: The open pull requests to compare it with.

    Returns:
        Claude's findings, limited to the pull requests it was shown.
    """
    if diff is None:
        shown = "GitHub did not render the diff because it is too large."
    else:
        kept, left_out = diffs.budget(diff, _DIFF_BUDGET)
        shown = kept + (
            f"\n\n({len(left_out)} more files left out)" if left_out else ""
        )
    body = pull.body[:_DESCRIPTION_LIMIT]
    if len(pull.body) > _DESCRIPTION_LIMIT:
        body += "\n(cut off here: the description is longer)"
    new = (
        f"#{pull.number}: {pull.title}\n"
        f"Author: {pull.author}; branch: {pull.head_ref}\n\n"
        f"Description:\n{body or '(none)'}\n\n"
        f"Changed files:\n{diffs.file_list(files, limit=100)}\n\n"
        f"Diff:\n{shown}"
    )
    catalog = "\n\n".join(_summary(other) for other in others)
    prompt = (
        f"The new pull request:\n{fence(new)}\n\n"
        f"The other open pull requests:\n{fence(catalog)}"
    )
    answer = claude.ask(
        system=COMPARE_SYSTEM, prompt=prompt, schema=_COMPARE_SCHEMA, effort="medium"
    )
    known = {other.number for other in others}
    return [
        item
        for item in answer.get("overlaps", [])
        if item.get("number") in known and item.get("relation") in RELATIONS
    ]


def find_overlaps(
    github: GitHub, claude: Claude | None, git: Git, number: int
) -> tuple[list[Overlap], str | None]:
    """Find the open pull requests that a pull request overlaps with.

    Args:
        github: The client.
        claude: The client for the purpose comparison, or None to skip it.
        git: The repository checkout, with full history of the base branch.
        number: The pull request.

    Returns:
        The strong overlaps, most urgent first, and a note about checks that could
        not run.
    """
    catalog = fetch_catalog(github)
    by_number = {pull.number: pull for pull in catalog}
    if number not in by_number:
        print(f"#{number} is no longer open")
        return [], None
    pull = by_number[number]
    files = github.pull_files(number)
    paths = {entry["filename"] for entry in files} | {
        entry["previous_filename"] for entry in files if entry.get("previous_filename")
    }
    linked = references(f"{pull.title}\n{pull.body}", github.repository)
    issues = pull.issues | (linked - by_number.keys())
    others = [
        other
        for other in catalog
        if other.number != number
        and other.number not in linked
        and other.base_ref == pull.base_ref
        and not same_login(other.author, pull.author)
    ]
    overlaps = {}
    for other in others:
        other_issues = other.issues | (
            references(f"{other.title}\n{other.body}", github.repository)
            - by_number.keys()
        )
        overlaps[other.number] = Overlap(
            other,
            shared=sorted(
                path for path in paths & other.files if not diffs.is_generated(path)
            ),
            issues=sorted(issues & other_issues),
        )
    # Two pull requests can only conflict in a file both change.
    sharing = [n for n, overlap in overlaps.items() if overlap.shared]
    conflicts, note = (
        simulate_conflicts(git, pull.base_ref, number, sharing)
        if sharing
        else ({}, None)
    )
    for other_number, paths_in_conflict in conflicts.items():
        overlaps[other_number].conflicts = paths_in_conflict
    if claude is not None and others:
        try:
            findings = compare(claude, pull, files, github.pull_diff(number), others)
        except (ClaudeError, anthropic.APIError) as error:
            print(f"::warning::#{number}: could not compare pull requests: {error}")
        else:
            for item in findings:
                overlap = overlaps[item["number"]]
                overlap.relation = item["relation"]
                overlap.explanation = str(item["explanation"])
    found = sorted(
        (overlap for overlap in overlaps.values() if overlap.strong),
        key=lambda overlap: (-overlap.rank, -overlap.pull.number),
    )
    return found[:_MAX_REPORTED], note


def render(overlaps: list[Overlap], note: str | None) -> str:
    """Write the overlap comment.

    Args:
        overlaps: The strong overlaps, most urgent first.
        note: A note about checks that could not run.

    Returns:
        The comment's Markdown.
    """
    lines = [comments.marker(PURPOSE)]
    if not overlaps:
        today = datetime.now(timezone.utc).date().isoformat()
        lines.append(f"No overlap with other open pull requests found ({today}).")
    else:
        lines.extend([
            "**Possible overlap with other open pull requests**",
            "",
            (
                "Landing one of these may conflict with or duplicate the other, so "
                "it may be worth choosing between them or agreeing on an order."
            ),
            "",
        ])
    for overlap in overlaps:
        pull = overlap.pull
        title = comments.sanitize(pull.title, 120)
        lines.append(f"- #{pull.number}: {title} (by {pull.author})")
        if overlap.relation:
            explanation = comments.sanitize(overlap.explanation, 300)
            lines.append(f"  - {_RELATION_TEXT[overlap.relation]}: {explanation}")
        if overlap.conflicts:
            lines.append(
                f"  - Conflicts with this pull request in {comments.code(overlap.conflicts, 5)}."
            )
        elif overlap.shared:
            lines.append(f"  - Also changes {comments.code(overlap.shared, 5)}.")
        if overlap.issues:
            issues = ", ".join(f"#{n}" for n in overlap.issues)
            lines.append(f"  - Both reference {issues}.")
    if note:
        lines.extend(["", note])
    lines.extend([
        "",
        (
            "<sub>Checked when this pull request was opened: conflicts by merging "
            "both pull requests onto the base branch, purpose by Claude reading the "
            f"descriptions and diffs. [How it works]({comments.README})</sub>"
        ),
    ])
    return "\n".join(lines)


def run(
    github: GitHub,
    claude: Claude | None,
    git: Git,
    number: int,
    write: comments.Writer,
) -> None:
    """Check a pull request for overlaps and comment on what was found.

    Args:
        github: The client.
        claude: The client for the purpose comparison, or None to skip it.
        git: The repository checkout, with full history of the base branch.
        number: The pull request.
        write: Makes (or, in a dry run, skips) each change.
    """
    overlaps, note = find_overlaps(github, claude, git, number)
    existing = comments.find(comments.all_comments(github, number), PURPOSE)
    # Without overlaps, only correct an earlier comment; never post a negative.
    outcome = comments.upsert(
        github,
        number,
        render(overlaps, note),
        existing,
        write,
        create=bool(overlaps),
    )
    found = ", ".join(f"#{overlap.pull.number}" for overlap in overlaps) or "none"
    print(f"#{number}: overlaps {found}; comment {outcome}")
