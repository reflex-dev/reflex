"""Unit tests for scripts/pr_bot/__main__.py (the bot's command line)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from scripts.pr_bot import __main__ as cli
from scripts.pr_bot import on_deck, pulls, triage
from tests.units.pr_bot.conftest import FakeGitHub, pull_request


@pytest.fixture
def github(monkeypatch: pytest.MonkeyPatch) -> FakeGitHub:
    """Make the command line use a fake GitHub, with no Anthropic key.

    Args:
        monkeypatch: The monkeypatch fixture.

    Returns:
        The fake.
    """
    fake = FakeGitHub()
    monkeypatch.setattr(cli.GitHub, "from_env", classmethod(lambda cls: fake))
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    return fake


def test_triage_needs_exactly_one_target():
    with pytest.raises(SystemExit):
        cli.main(["triage"])
    with pytest.raises(SystemExit):
        cli.main(["triage", "--all", "--pr", "1"])


def test_triage_dry_run_of_one_pull_request(
    github: FakeGitHub,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
):
    github.route("GET", "repos/reflex-dev/reflex/labels", [])
    monkeypatch.setattr(
        pulls, "fetch", lambda client, number: pull_request(number=number)
    )
    assert cli.main(["triage", "--pr", "7", "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "Dry run: nothing on GitHub is changed." in out
    assert "ANTHROPIC_API_KEY is not set" in out
    assert (
        "#7: waiting on maintainer, complexity unknown; labels +status: waiting on maintainer; comment created"
        in out
    )
    assert github.writes() == []


def test_triage_by_head_branch(github: FakeGitHub, monkeypatch: pytest.MonkeyPatch):
    seen: list[Any] = []
    monkeypatch.setattr(
        triage,
        "find_by_head",
        lambda client, owner, branch: seen.append((owner, branch)) or [],
    )
    assert cli.main(["triage", "--head", "contributor:feature/x:y"]) == 0
    assert seen == [("contributor", "feature/x:y")]


def test_on_deck_find_hands_candidates_to_the_workflow(
    github: FakeGitHub, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    candidate = on_deck.Candidate(
        7, "a" * 40, "main", "b" * 40, "o/r", "x';rm -rf /", True
    )
    monkeypatch.setattr(on_deck, "find", lambda client, git, forced: [candidate])
    output = tmp_path / "output"
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))
    assert cli.main(["on-deck", "find", "--force", "7"]) == 0
    name, _, value = output.read_text().strip().partition("=")
    assert name == "prs"
    (entry,) = json.loads(value)
    assert cli._candidate(json.dumps(entry)) == candidate
