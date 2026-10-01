"""Command line for the pull request bot: ``python -m scripts.pr_bot <command>``.

Every command reads ``GITHUB_TOKEN`` and ``GITHUB_REPOSITORY``; the ones that ask
Claude read ``ANTHROPIC_API_KEY`` and skip their judgments without it.
``--dry-run`` reports what a command would change without changing it.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import os
import sys
from collections.abc import Sequence
from pathlib import Path

from scripts.pr_bot import comments, on_deck, overlap, pulls, status, triage
from scripts.pr_bot.git import Git
from scripts.pr_bot.github import GitHub
from scripts.pr_bot.llm import Claude

REPO_ROOT = Path(__file__).parents[2]


def _claude() -> Claude | None:
    """Create the Claude client when an API key is configured.

    Returns:
        The client, or None when ``ANTHROPIC_API_KEY`` is unset.
    """
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print(
            "::warning::ANTHROPIC_API_KEY is not set, so Claude's judgments are skipped."
        )
        return None
    return Claude()


def _set_output(name: str, value: str) -> None:
    """Hand a value to later workflow steps, or print it outside a workflow.

    Args:
        name: The output's name.
        value: Its value, on one line.
    """
    line = f"{name}={value}\n"
    path = os.environ.get("GITHUB_OUTPUT")
    if path:
        with Path(path).open("a", encoding="utf-8") as output:
            output.write(line)
    else:
        print(line, end="")


def _triage(args: argparse.Namespace) -> int:
    """Run the triage command.

    Args:
        args: The parsed arguments.

    Returns:
        The exit status.
    """
    github = GitHub.from_env()
    runner = triage.Triage(
        github=github,
        claude=_claude(),
        required=status.required_checks(),
        estimates_left=args.max_estimates,
        # A sweep can relabel every open pull request at once.
        write=comments.writer(dry_run=args.dry_run, pause=1.0 if args.all else 0.0),
    )
    if args.all:
        return 1 if runner.sweep() else 0
    numbers = args.pr or []
    if args.head:
        owner, _, branch = args.head.partition(":")
        numbers = triage.find_by_head(github, owner, branch)
    for number in numbers:
        runner.triage(pulls.fetch(github, number))
    return 0


def _overlap(args: argparse.Namespace) -> int:
    """Run the overlap command.

    Args:
        args: The parsed arguments.

    Returns:
        The exit status.
    """
    overlap.run(
        GitHub.from_env(),
        _claude(),
        Git(REPO_ROOT),
        args.pr,
        comments.writer(dry_run=args.dry_run),
    )
    return 0


def _candidate(raw: str) -> on_deck.Candidate:
    """Parse a candidate handed from the find job through the job matrix.

    Args:
        raw: The candidate as JSON.

    Returns:
        The candidate.
    """
    return on_deck.Candidate(**json.loads(raw))


def _on_deck(args: argparse.Namespace) -> int:
    """Run a step of the on-deck command.

    Args:
        args: The parsed arguments.

    Returns:
        The exit status.
    """
    git = Git(REPO_ROOT)
    if args.step == "find":
        found = on_deck.find(GitHub.from_env(), git, forced=args.force)
        _set_output("prs", json.dumps([dataclasses.asdict(c) for c in found]))
    elif args.step == "prepare":
        outcome = on_deck.prepare(
            GitHub.from_env(),
            git,
            candidate=_candidate(args.candidate),
            worktree=args.worktree,
            context=args.context,
            out=args.out,
        )
        _set_output("status", outcome)
    elif args.step == "finalize":
        result = on_deck.finalize(
            candidate=_candidate(args.candidate),
            worktree=args.worktree,
            context=args.context,
            agent_output=args.agent_output,
            out=args.out,
        )
        print(f"Resolution {result['status']}: {result.get('reason', '')}")
    else:
        outcome = on_deck.push(
            GitHub.from_env(),
            git,
            number=args.pr,
            artifact=args.artifact,
            token=os.environ["GITHUB_TOKEN"],
            app_slug=args.app_slug,
            write=comments.writer(dry_run=args.dry_run),
        )
        print(f"#{args.pr}: {outcome}")
    return 0


def _parser() -> argparse.ArgumentParser:
    """Describe the command line.

    Returns:
        The parser.
    """
    parser = argparse.ArgumentParser(prog="python -m scripts.pr_bot")
    commands = parser.add_subparsers(dest="command", required=True)

    run = commands.add_parser(
        "triage", help="label pull requests by status and complexity"
    )
    target = run.add_mutually_exclusive_group(required=True)
    target.add_argument("--pr", type=int, action="append", help="a pull request number")
    target.add_argument("--head", help="the OWNER:BRANCH a pull request is from")
    target.add_argument("--all", action="store_true", help="every open pull request")
    run.add_argument(
        "--max-estimates",
        type=int,
        default=20,
        help="the most complexity estimates to make (each is a Claude request)",
    )
    run.add_argument("--dry-run", action="store_true")

    run = commands.add_parser(
        "overlap", help="find open pull requests one overlaps with"
    )
    run.add_argument("--pr", type=int, required=True)
    run.add_argument("--dry-run", action="store_true")

    run = commands.add_parser(
        "on-deck", help="resolve conflicts on on-deck pull requests"
    )
    steps = run.add_subparsers(dest="step", required=True)
    step = steps.add_parser("find")
    step.add_argument(
        "--force",
        type=int,
        metavar="PR",
        help="retry this pull request even if the bot failed on its current head",
    )
    prepare = steps.add_parser("prepare")
    finalize = steps.add_parser("finalize")
    for step in (prepare, finalize):
        step.add_argument("--candidate", required=True, help="the find step's entry")
        step.add_argument("--worktree", type=Path, required=True)
        step.add_argument("--context", type=Path, required=True)
        step.add_argument("--out", type=Path, required=True)
    finalize.add_argument("--agent-output", type=Path, required=True)
    step = steps.add_parser("push")
    step.add_argument("--pr", type=int, required=True)
    step.add_argument("--artifact", type=Path, required=True)
    step.add_argument("--app-slug", required=True)
    step.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the bot.

    Args:
        argv: The arguments; the process's own by default.

    Returns:
        The exit status.
    """
    args = _parser().parse_args(argv)
    if getattr(args, "dry_run", False):
        print("Dry run: nothing on GitHub is changed.")
    handlers = {"triage": _triage, "overlap": _overlap, "on-deck": _on_deck}
    return handlers[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
