"""Functions to communicate to the user via console."""

from __future__ import annotations

from typing import List, Optional

from rich.console import Console
from rich.prompt import Prompt
from rich.status import Status

from reflex.constants import LogLevel

# Console for pretty printing.
_console = Console()

# The current log level.
LOG_LEVEL = LogLevel.INFO


def print(msg: str):
    """Print a message.

    Args:
        msg: The message to print.
    """
    _console.print(msg)

def debug(msg: str):
    """Print a debug message.

    Args:
        msg: The debug message.
    """
    if LOG_LEVEL <= LogLevel.DEBUG:
        print(f"[blue]Debug: {msg}[/blue]")


def info(msg: str):
    """Print an info message.

    Args:
        msg: The info message.
    """
    if LOG_LEVEL <= LogLevel.INFO:
       print(f"[green]Info: {msg}[/green]")


def log(msg: str):
    """Takes a string and logs it to the console.

    Args:
        msg: The message to log.
    """
    if LOG_LEVEL <= LogLevel.INFO:
        _console.log(msg)


def rule(title: str):
    """Prints a horizontal rule with a title.

    Args:
        title: The title of the rule.
    """
    _console.rule(title)


def warn(msg: str):
    """Print a warning message.

    Args:
        msg: The warning message.
    """
    if LOG_LEVEL <= LogLevel.WARNING:
        print(f"[orange1]Warning: {msg}[/orange1]")

def deprecate(msg: str):
    """Print a deprecation warning.

    Args:
        msg: The deprecation message.
    """
    if LOG_LEVEL <= LogLevel.WARNING:
        print(f"[yellow]DeprecationWarning: {msg}[/yellow]")


def error(msg: str):
    """Print an error message.

    Args:
        msg: The error message.
    """
    if LOG_LEVEL <= LogLevel.ERROR:
        print(f"[red]Error: {msg}[/red]")


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
        A string with the user input.
    """
    return Prompt.ask(question, choices=choices, default=default)  # type: ignore
