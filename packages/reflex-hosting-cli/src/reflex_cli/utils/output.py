"""Machine-readable output, and the shared options that turn it on.

An agent driving the cloud CLI needs two things a person at a terminal does
not: output it can parse without regexing a Rich table, and the certainty that
nothing will stop and wait for a keystroke. ``--json`` answers the first and
reserves stdout for the document while it does; ``--interactive`` answers the
second by defaulting to whether stdout is a terminal.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Sequence
from typing import Any

import click

# Through the CLI's own shim, not reflex_base directly: the hosting CLI has to
# import against a reflex-base that predates these functions, which is what
# tests/units/reflex_cli/utils/test_log.py pins.
from reflex_cli.utils import log

# The spellings that ask for JSON on the command line, and the one that
# refuses it. Read straight off argv so the group callback can reserve stdout
# before click has parsed the subcommand's options -- anything it says would
# otherwise land on stdout ahead of the document.
_JSON_FLAGS = frozenset({"--json", "-j"})
_JSON_SHORT = "j"
_NO_JSON_FLAG = "--no-json"


def _json_flag_state(arg: str) -> bool | None:
    """Read what one command-line argument says about JSON output.

    Args:
        arg: A single command-line argument.

    Returns:
        True if it asks for JSON, False if it refuses it, None if it says
        nothing either way.
    """
    if arg == _NO_JSON_FLAG:
        return False
    if arg in _JSON_FLAGS:
        return True
    # Short flags combine, so `-ij` is `-i -j`. Reading them means this scan
    # can also fire on a `-j` that click would take as some other option's
    # value, which is the direction to be wrong in: a message on stderr costs
    # a little context, one inside the document costs the whole parse.
    return (
        True
        if len(arg) > 1
        and arg.startswith("-")
        and not arg.startswith("--")
        and _JSON_SHORT in arg[1:]
        else None
    )


def stdout_is_tty() -> bool:
    """Check whether stdout is attached to a terminal.

    Returns:
        True if somebody is plausibly watching, False under a pipe, a CI job
        or an agent.
    """
    isatty = getattr(sys.stdout, "isatty", None)
    if isatty is None:
        return False
    try:
        return bool(isatty())
    except ValueError:
        # A closed stream. Nobody is answering a prompt on it either way.
        return False


def _resolve_interactive(
    ctx: click.Context, param: click.Parameter, value: bool | None
) -> bool:
    """Resolve an unset ``--interactive`` against the terminal.

    Args:
        ctx: The click context.
        param: The click parameter.
        value: The flag's value, or None when neither spelling was passed.

    Returns:
        Whether the command may prompt.
    """
    return stdout_is_tty() if value is None else value


interactive_option = click.option(
    "--interactive/--no-interactive",
    "-i/",
    "interactive",
    default=None,
    callback=_resolve_interactive,
    help="Whether to prompt for confirmations and choices. Defaults to on when "
    "stdout is a terminal and off otherwise, so a pipe, a CI job or an agent is "
    "never left waiting at a prompt.",
)


def json_requested(argv: Sequence[str] | None = None) -> bool:
    """Check whether a command line asks for JSON output.

    Scanned back to front, so the last flag decides -- the same answer click
    reaches for a boolean flag pair, which a set membership test cannot give:
    ``--no-json --json`` enables JSON and ``--json --no-json`` does not.

    Args:
        argv: The arguments to inspect; defaults to this process's own.

    Returns:
        True if the command line asks for JSON output.
    """
    args = sys.argv[1:] if argv is None else argv
    for arg in reversed(list(args)):
        if (state := _json_flag_state(arg)) is not None:
            return state
    return False


def _hold_reservation(ctx: click.Context, reserved: bool) -> None:
    """Reserve stdout for this context, releasing it again when it closes.

    The reservation is process-global, so without an explicit release a
    ``--json`` command leaves every later log line in the process writing to
    stderr -- which a CLI process never notices, and an embedding one or a
    second run in the same interpreter does.

    Args:
        ctx: The click context whose lifetime the reservation follows.
        reserved: Whether stdout carries data rather than human output.
    """
    previous = log.is_stdout_reserved()
    log.reserve_stdout(reserved)
    ctx.call_on_close(lambda: log.reserve_stdout(previous))


def reserve_stdout_for_argv(
    argv: Sequence[str] | None = None, *, ctx: click.Context | None = None
) -> None:
    """Reserve stdout up front when the command line asks for JSON.

    Always writes the reservation rather than only setting it, so a long-lived
    process (tests, an embedded runner) cannot inherit the previous
    invocation's answer.

    Args:
        argv: The arguments to inspect; defaults to this process's own.
        ctx: The click context to release the reservation with, if there is one.
    """
    reserved = json_requested(argv)
    if ctx is None:
        log.reserve_stdout(reserved)
        return
    _hold_reservation(ctx, reserved)


def _reserve_stdout(ctx: click.Context, param: click.Parameter, value: bool) -> bool:
    """Reserve stdout for the document once ``--json`` is parsed.

    Args:
        ctx: The click context.
        param: The click parameter.
        value: Whether JSON output was asked for.

    Returns:
        The flag's value, unchanged.
    """
    if value:
        _hold_reservation(ctx, True)
    return value


json_option = click.option(
    "--json/--no-json",
    "-j",
    "as_json",
    is_flag=True,
    is_eager=True,
    callback=_reserve_stdout,
    help="Output the result as a single JSON document on stdout. Human-readable "
    "messages go to stderr instead, so stdout stays parseable.",
)


def print_json(payload: Any) -> None:
    """Write one JSON document to stdout.

    Deliberately not routed through :mod:`reflex_cli.utils.console`: this is the
    output the command was asked for, not a message about it, so it goes to
    stdout even while the console renders to stderr, and is never wrapped in a
    log record.

    Args:
        payload: The value to serialize.
    """
    click.echo(json.dumps(payload, default=str))
