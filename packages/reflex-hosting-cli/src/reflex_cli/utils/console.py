"""Functions to communicate to the user via console."""

from __future__ import annotations

from collections.abc import Sequence
from typing import overload

from rich.console import Console

from reflex_cli.constants import LogLevel

# Console for pretty printing.
_console = Console()

# The current log level.
_LOG_LEVEL = LogLevel.INFO


def set_log_level(log_level: LogLevel | str):
    """Set the log level.

    Args:
        log_level: The log level to set.

    """
    if isinstance(log_level, str):
        try:
            log_level = LogLevel(log_level)
        except ValueError:
            log_level = LogLevel.INFO
    global _LOG_LEVEL
    _LOG_LEVEL = log_level


def print(msg: str, **kwargs):
    """Print a message.

    Args:
        msg: The message to print.
        kwargs: Keyword arguments to pass to the print function.

    """
    _console.print(msg, **kwargs)


def print_table(
    tabular_data: list[list[str]],
    headers: Sequence[str] = (),
) -> None:
    """Print a table to the console.

    Args:
        tabular_data: The data to print in tabular format.
        headers: The headers for the table.
    """
    from rich.table import Table

    table = Table()

    for column in headers:
        table.add_column(column)

    for row in tabular_data:
        table.add_row(*row)

    _console.print(table)


def debug(msg: str, **kwargs):
    """Print a debug message.

    Args:
        msg: The debug message.
        kwargs: Keyword arguments to pass to the print function.

    """
    if _LOG_LEVEL <= LogLevel.DEBUG:
        print(f"[blue]Debug: {msg}[/blue]", **kwargs)


def info(msg: str, **kwargs):
    """Print an info message.

    Args:
        msg: The info message.
        kwargs: Keyword arguments to pass to the print function.

    """
    if _LOG_LEVEL <= LogLevel.INFO:
        print(f"[cyan]Info: {msg}[/cyan]", **kwargs)


def success(msg: str, **kwargs):
    """Print a success message.

    Args:
        msg: The success message.
        kwargs: Keyword arguments to pass to the print function.

    """
    if _LOG_LEVEL <= LogLevel.WARNING:
        print(f"[green]Success: {msg}[/green]", **kwargs)


def log(msg: str, **kwargs):
    """Takes a string and logs it to the console.

    Args:
        msg: The message to log.
        kwargs: Keyword arguments to pass to the print function.

    """
    if _LOG_LEVEL <= LogLevel.INFO:
        _console.log(msg, **kwargs)


def rule(title: str, **kwargs):
    """Prints a horizontal rule with a title.

    Args:
        title: The title of the rule.
        kwargs: Keyword arguments to pass to the print function.

    """
    _console.rule(title, **kwargs)


def warn(msg: str, **kwargs):
    """Print a warning message.

    Args:
        msg: The warning message.
        kwargs: Keyword arguments to pass to the print function.

    """
    if _LOG_LEVEL <= LogLevel.WARNING:
        print(f"[orange1]Warning: {msg}[/orange1]", **kwargs)


def error(msg: str, **kwargs):
    """Print an error message.

    Args:
        msg: The error message.
        kwargs: Keyword arguments to pass to the print function.

    """
    if _LOG_LEVEL <= LogLevel.ERROR:
        print(f"[red]{msg}[/red]", **kwargs)


@overload
def ask(
    question: str,
    *,
    choices: list[str] | None = None,
    show_choices: bool = True,
) -> str: ...


@overload
def ask(
    question: str,
    *,
    default: str,
    choices: list[str] | None = None,
    show_choices: bool = True,
) -> str: ...


def ask(
    question: str,
    *,
    choices: list[str] | None = None,
    show_choices: bool = True,
    default: str | None = None,
) -> str | None:
    """Takes a prompt question and optionally a list of choices
     and returns the user input.

    Args:
        question: The question to ask the user.
        choices: A list of choices to select from.
        show_choices: Whether to show the choices.
        default: The default option selected.

    Returns:
        A string with the user input.

    """
    from rich.prompt import Prompt

    return Prompt.ask(
        question, choices=choices, default=default, show_choices=show_choices
    )


def progress():
    """Create a new progress bar.


    Returns:
        A new progress bar.

    """
    from rich.progress import MofNCompleteColumn, Progress, TimeElapsedColumn

    return Progress(
        *Progress.get_default_columns()[:-1],
        MofNCompleteColumn(),
        TimeElapsedColumn(),
    )


def status(*args, **kwargs):
    """Create a status with a spinner.

    Args:
        *args: Args to pass to the status.
        **kwargs: Kwargs to pass to the status.

    Returns:
        A new status.

    """
    return _console.status(*args, **kwargs)
