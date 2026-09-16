"""Tests for the shared machine-readable output options in reflex_cli.utils.output."""

import io
import json

import click
import pytest
from click.testing import CliRunner
from pytest_mock import MockFixture
from reflex_base.utils import log
from reflex_cli.utils import output

runner = CliRunner()


@pytest.fixture(autouse=True)
def _release_stdout():
    """Release any stdout reservation a test left behind.

    Yields:
        None.
    """
    yield
    log.reserve_stdout(False)


@click.command()
@output.json_option
@output.interactive_option
def _probe(as_json: bool, interactive: bool):
    """Report the resolved flags and whether stdout was reserved."""
    output.print_json({
        "as_json": as_json,
        "interactive": interactive,
        "stdout_reserved": log.is_stdout_reserved(),
    })


def test_stdout_is_tty_false_for_a_plain_stream(monkeypatch):
    """A stream nobody is watching is not a terminal."""
    monkeypatch.setattr("sys.stdout", io.StringIO())
    assert output.stdout_is_tty() is False


def test_stdout_is_tty_true_for_a_terminal(monkeypatch):
    """A stream that claims to be a terminal is one."""
    stream = io.StringIO()
    monkeypatch.setattr(stream, "isatty", lambda: True)
    monkeypatch.setattr("sys.stdout", stream)
    assert output.stdout_is_tty() is True


def test_stdout_is_tty_false_for_a_closed_stream(monkeypatch):
    """A closed stream answers False rather than raising."""
    stream = io.StringIO()
    stream.close()
    monkeypatch.setattr("sys.stdout", stream)
    assert output.stdout_is_tty() is False


def test_stdout_is_tty_false_when_the_stream_has_no_isatty(monkeypatch):
    """A replacement stdout without isatty is not a terminal."""
    monkeypatch.setattr("sys.stdout", object())
    assert output.stdout_is_tty() is False


# Every spelling that has to agree with click, since the scan runs before
# click parses and decides where the group callback's own output goes.
_JSON_ARGV_CASES = [
    ([], False),
    (["apps", "list"], False),
    (["apps", "list", "--json"], True),
    (["apps", "list", "-j"], True),
    (["apps", "list", "--no-json"], False),
    # Last flag wins, in both directions: click parses these as a pair, so a
    # membership test that answers "--no-json is present" is wrong about the
    # second one.
    (["apps", "list", "--json", "--no-json"], False),
    (["apps", "list", "--no-json", "--json"], True),
    # Short flags combine.
    (["apps", "list", "-ij"], True),
    (["apps", "list", "-ji"], True),
]


@pytest.mark.parametrize(("argv", "expected"), _JSON_ARGV_CASES)
def test_json_requested(argv: list[str], expected: bool):
    """A JSON flag on the command line is recognized before click parses it.

    Args:
        argv: The arguments to inspect.
        expected: Whether they ask for JSON.
    """
    assert output.json_requested(argv) is expected


@pytest.mark.parametrize(("argv", "expected"), _JSON_ARGV_CASES)
def test_json_requested_agrees_with_click(argv: list[str], expected: bool):
    """The pre-parse scan reaches the same answer click's parser does.

    The scan only exists to route output emitted before parsing, so a
    disagreement puts a log line on the stdout a document is about to own.

    Args:
        argv: The arguments to inspect.
        expected: Whether they ask for JSON.
    """
    result = runner.invoke(_probe, argv[2:])

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["as_json"] is expected


def test_reserve_stdout_for_argv_clears_a_stale_reservation():
    """A command line without --json releases a previous reservation."""
    log.reserve_stdout(True)
    output.reserve_stdout_for_argv(["apps", "list"])
    assert log.is_stdout_reserved() is False


def test_interactive_defaults_off_without_a_terminal(mocker: MockFixture):
    """Nothing prompts when stdout is a pipe, a CI job or an agent."""
    mocker.patch("reflex_cli.utils.output.stdout_is_tty", return_value=False)

    result = runner.invoke(_probe, [])

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["interactive"] is False


def test_interactive_defaults_on_with_a_terminal(mocker: MockFixture):
    """A person at a terminal still gets the prompts."""
    mocker.patch("reflex_cli.utils.output.stdout_is_tty", return_value=True)

    result = runner.invoke(_probe, [])

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["interactive"] is True


@pytest.mark.parametrize(
    ("flag", "expected"),
    [("--interactive", True), ("-i", True), ("--no-interactive", False)],
)
def test_explicit_interactive_flag_beats_the_terminal(
    mocker: MockFixture, flag: str, expected: bool
):
    """An explicit flag decides regardless of what stdout is.

    Args:
        mocker: The pytest-mock fixture.
        flag: The spelling passed on the command line.
        expected: The value it resolves to.
    """
    mocker.patch("reflex_cli.utils.output.stdout_is_tty", return_value=not expected)

    result = runner.invoke(_probe, [flag])

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["interactive"] is expected


def test_json_flag_reserves_stdout_before_the_command_runs():
    """The reservation is in place by the time the body can log anything."""
    result = runner.invoke(_probe, ["--json"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["as_json"] is True
    assert payload["stdout_reserved"] is True


def test_no_json_leaves_stdout_unreserved():
    """Without --json, human-readable output keeps stdout."""
    result = runner.invoke(_probe, [])

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["stdout_reserved"] is False


def test_reservation_is_released_when_the_command_ends():
    """The reservation lasts the command, not the process.

    A CLI process exits and never notices, but an embedding one -- or a second
    run in the same interpreter -- would have every later log line writing to
    stderr on behalf of a command that finished.
    """
    result = runner.invoke(_probe, ["--json"])

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["stdout_reserved"] is True
    assert log.is_stdout_reserved() is False


def test_a_later_command_is_not_reserved_by_an_earlier_one():
    """A plain run after a --json run still writes to stdout."""
    runner.invoke(_probe, ["--json"])

    result = runner.invoke(_probe, [])

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["stdout_reserved"] is False


def test_print_json_writes_one_document_while_the_console_writes_to_stderr():
    """The document owns stdout even while messages are being printed.

    This is what makes ``--json`` parseable: a warning from a helper deep in
    the call stack would otherwise land in the middle of the document.
    """
    from reflex_cli.utils import console

    @click.command()
    @output.json_option
    def noisy(as_json: bool):
        """Print a message and then the document."""
        console.print("a message for a person")
        output.print_json({"ok": True})

    result = runner.invoke(noisy, ["--json"])

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == {"ok": True}
    assert "a message for a person" in result.stderr


def test_print_json_serializes_values_json_cannot():
    """A value without a JSON form is rendered as its string, not an error."""

    @click.command()
    def pathy():
        """Print a payload holding a non-serializable value."""
        from pathlib import Path

        output.print_json({"path": Path("cloud.yml")})

    result = runner.invoke(pathy, [])

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == {"path": "cloud.yml"}
