"""The two triage judgments Claude makes: complexity, and what comments ask for."""

from __future__ import annotations

import dataclasses
from typing import Any

from scripts.pr_bot import diffs
from scripts.pr_bot.llm import Claude, ClaudeError, fence
from scripts.pr_bot.pulls import PullRequest
from scripts.pr_bot.status import Request

LEVELS = ("low", "medium", "high")
# Room for the diff in the complexity prompt (about 40k tokens), so one large pull
# request costs cents rather than dollars. The prompt says what was left out.
DIFF_BUDGET = 150_000
_COMMENT_LIMIT = 4_000

COMPLEXITY_SYSTEM = """\
You estimate how much review a pull request to Reflex needs. Reflex is a Python web \
framework that compiles apps to a React frontend. Its riskiest code is the state \
system and event processing (reflex/state.py, reflex/istate/, reflex/app.py), the Var \
system that turns Python expressions into JavaScript and the compiler \
(packages/reflex-base), and the frontend runtime it generates; the component \
libraries (packages/reflex-components-*) wrap React components.

Classify the pull request as one of:
- low: small and local, and its correctness shows in the diff itself. Typical: \
documentation, typos, tests only, a contained bug fix with a test, a dependency bump, \
a CI or configuration tweak with an obvious effect.
- medium: a real logic change confined to one area, such as one component, one CLI \
command or one subsystem. A reviewer needs the surrounding code to judge it and \
could miss a regression.
- high: cross-cutting, architectural or risky. Typical: changes to state \
management, event processing, the compiler or the Var system; concurrency, \
serialization or security-sensitive code; new or changed public APIs; breaking \
changes; large refactors; new packages. It needs deep review or a design discussion.

Judge by what a careful reviewer must understand, not by line count: lockfiles, \
generated stubs, snapshots and documentation add size without risk, while a ten-line \
change to locking can be high. State the rationale in one sentence naming what \
drives the estimate."""

_COMPLEXITY_SCHEMA = {
    "type": "object",
    "properties": {
        "complexity": {"type": "string", "enum": list(LEVELS)},
        "rationale": {"type": "string"},
    },
    "required": ["complexity", "rationale"],
    "additionalProperties": False,
}

JUDGE_SYSTEM = """\
Maintainers of the Reflex repository left these comments on a pull request that \
someone else opened. For each comment, decide whether it asks the pull request's \
author to do something before the review can continue: change or explain code, \
answer a question, add tests or documentation, rebase, split the change, and so on. \
A comment does not ask the author when it only acknowledges or thanks them, talks \
to another maintainer, records what the maintainer will do next, or approves \
without conditions."""

_JUDGE_SCHEMA = {
    "type": "object",
    "properties": {
        "verdicts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "asks_author": {"type": "boolean"},
                },
                "required": ["id", "asks_author"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["verdicts"],
    "additionalProperties": False,
}


@dataclasses.dataclass(frozen=True)
class Estimate:
    """A complexity estimate."""

    level: str
    rationale: str


def complexity_prompt(
    pr: PullRequest, files: list[dict[str, Any]], diff: str | None
) -> str:
    """Build the material for a complexity estimate.

    Args:
        pr: The pull request.
        files: Its entries of the pulls files API.
        diff: Its unified diff, or None when GitHub would not render it.

    Returns:
        The prompt.
    """
    if diff is None:
        shown = "GitHub did not render the diff because it is too large."
    else:
        kept, left_out = diffs.budget(diff, DIFF_BUDGET)
        shown = kept or "(no hand-written changes)"
        if left_out:
            shown += (
                f"\n\nLeft out of the diff ({len(left_out)} files, generated or over "
                f"the size budget): {', '.join(left_out[:100])}"
            )
    details = (
        f"Title: {pr.title}\n"
        f"Branch: {pr.head_ref} into {pr.base_ref}\n"
        f"Size: +{pr.additions} -{pr.deletions} in {pr.changed_files} files\n\n"
        f"Description:\n{pr.body or '(none)'}\n\n"
        f"Changed files:\n{diffs.file_list(files)}\n\n"
        f"Diff:\n{shown}"
    )
    return f"Estimate the complexity of this pull request.\n\n{fence(details)}"


def estimate_complexity(
    claude: Claude, pr: PullRequest, files: list[dict[str, Any]], diff: str | None
) -> Estimate:
    """Estimate how much review a pull request needs.

    Args:
        claude: The client.
        pr: The pull request.
        files: Its entries of the pulls files API.
        diff: Its unified diff, or None when GitHub would not render it.

    Returns:
        The estimate.

    Raises:
        ClaudeError: If the answer is not one of the levels.
    """
    answer = claude.ask(
        system=COMPLEXITY_SYSTEM,
        prompt=complexity_prompt(pr, files, diff),
        schema=_COMPLEXITY_SCHEMA,
    )
    if answer.get("complexity") not in LEVELS:
        msg = f"unexpected complexity {answer.get('complexity')!r}"
        raise ClaudeError(msg)
    return Estimate(answer["complexity"], str(answer.get("rationale", "")))


def judge_requests(
    claude: Claude, pr: PullRequest, requests: list[Request]
) -> dict[str, bool]:
    """Decide which maintainer comments ask the author for something.

    Args:
        claude: The client.
        pr: The pull request they were left on.
        requests: The comments to judge.

    Returns:
        For each comment's node id, whether it asks the author to act. Ids Claude
        did not answer for are left out, so they are asked again next time.
    """
    entries = "\n\n".join(
        f"Comment {request.node_id} by {request.author.display}:\n"
        + (
            request.body
            if len(request.body) <= _COMMENT_LIMIT
            else f"{request.body[:_COMMENT_LIMIT]}\n(cut off here: the comment is longer)"
        )
        for request in requests
    )
    prompt = (
        f"Pull request #{pr.number}, opened by {pr.author.display}: {pr.title}\n\n"
        f"Judge each of these comments, answering with its id.\n\n{fence(entries)}"
    )
    answer = claude.ask(
        system=JUDGE_SYSTEM, prompt=prompt, schema=_JUDGE_SCHEMA, effort="low"
    )
    asked = {request.node_id for request in requests}
    return {
        verdict["id"]: bool(verdict["asks_author"])
        for verdict in answer.get("verdicts", [])
        if verdict.get("id") in asked
    }
