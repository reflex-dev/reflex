"""Functions to communicate to the user via console."""

from __future__ import annotations

from typing import List, Optional

from rich.console import Console
from rich.prompt import Prompt
from rich.status import Status

# Console for pretty printing.
_console = Console()


def deprecate(msg: str) -> None:
    """Print a deprecation warning.

    Args:
        msg: The deprecation message.
    """
    _console.print(f"[yellow]DeprecationWarning: {msg}[/yellow]")


def log(msg: str) -> None:
    """Takes a string and logs it to the console.

    Args:
        msg: The message to log.
    """
    _console.log(msg)


def print(msg: str) -> None:
    """Prints the given message to the console.

    Args:
        msg: The message to print to the console.
    """
    _console.print(msg)


def rule(title: str) -> None:
    """Prints a horizontal rule with a title.

    Args:
        title: The title of the rule.
    """
    _console.rule(title)


def ask(
    question: str, choices: Optional[List[str]] = None, default: Optional[str] = None
) -> str:
    """Takes a prompt question and optionally a list of choices
     and returns the user input.

    Args:
        question: The question to ask the user.
        choices: A list of choices to select from.
        default: The default option selected.

    Returns:
        A string
    """
    return Prompt.ask(question, choices=choices, default=default)  # type: ignore


def status(msg: str) -> Status:
    """Returns a status,
    which can be used as a context manager.

    Args:
        msg: The message to be used as status title.

    Returns:
        The status of the console.
    """
    return _console.status(msg)
