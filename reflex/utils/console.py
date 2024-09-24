"""Functions to communicate to the user via console."""

from __future__ import annotations

from rich.console import Console
from rich.progress import MofNCompleteColumn, Progress, TimeElapsedColumn
from rich.prompt import Prompt

from reflex.constants import LogLevel

# Console for pretty printing.
_console = Console()

# The current log level.
_LOG_LEVEL = LogLevel.INFO

# Deprecated features who's warning has been printed.
_EMITTED_DEPRECATION_WARNINGS = set()

# Info messages which have been printed.
_EMITTED_INFO = set()


def set_log_level(log_level: LogLevel):
    """Set the log level.

    Args:
        log_level: The log level to set.
    """
    global _LOG_LEVEL
    _LOG_LEVEL = log_level


def is_debug() -> bool:
    """Check if the log level is debug.

    Returns:
        True if the log level is debug.
    """
    return _LOG_LEVEL <= LogLevel.DEBUG


def print(msg: str, **kwargs):
    """Print a message.

    Args:
        msg: The message to print.
        kwargs: Keyword arguments to pass to the print function.
    """
    _console.print(msg, **kwargs)


def debug(msg: str, **kwargs):
    """Print a debug message.

    Args:
        msg: The debug message.
        kwargs: Keyword arguments to pass to the print function.
    """
    if is_debug():
        msg_ = f"[blue]Debug: {msg}[/blue]"
        if progress := kwargs.pop("progress", None):
            progress.console.print(msg_, **kwargs)
        else:
            print(msg_, **kwargs)


def info(msg: str, dedupe: bool = False, **kwargs):
    """Print an info message.

    Args:
        msg: The info message.
        dedupe: If True, suppress multiple console logs of info message.
        kwargs: Keyword arguments to pass to the print function.
    """
    if _LOG_LEVEL <= LogLevel.INFO:
        if dedupe:
            if msg in _EMITTED_INFO:
                return
            else:
                _EMITTED_INFO.add(msg)
        print(f"[cyan]Info: {msg}[/cyan]", **kwargs)


def success(msg: str, **kwargs):
    """Print a success message.

    Args:
        msg: The success message.
        kwargs: Keyword arguments to pass to the print function.
    """
    if _LOG_LEVEL <= LogLevel.INFO:
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


def deprecate(
    feature_name: str,
    reason: str,
    deprecation_version: str,
    removal_version: str,
    dedupe: bool = True,
    **kwargs,
):
    """Print a deprecation warning.

    Args:
        feature_name: The feature to deprecate.
        reason: The reason for deprecation.
        deprecation_version: The version the feature was deprecated
        removal_version: The version the deprecated feature will be removed
        dedupe: If True, suppress multiple console logs of deprecation message.
        kwargs: Keyword arguments to pass to the print function.
    """
    if feature_name not in _EMITTED_DEPRECATION_WARNINGS:
        msg = (
            f"{feature_name} has been deprecated in version {deprecation_version} {reason.rstrip('.')}. It will be completely "
            f"removed in {removal_version}"
        )
        if _LOG_LEVEL <= LogLevel.WARNING:
            print(f"[yellow]DeprecationWarning: {msg}[/yellow]", **kwargs)
        if dedupe:
            _EMITTED_DEPRECATION_WARNINGS.add(feature_name)


def error(msg: str, **kwargs):
    """Print an error message.

    Args:
        msg: The error message.
        kwargs: Keyword arguments to pass to the print function.
    """
    if _LOG_LEVEL <= LogLevel.ERROR:
        print(f"[red]{msg}[/red]", **kwargs)


def ask(
    question: str,
    choices: list[str] | None = None,
    default: str | None = None,
    show_choices: bool = True,
) -> str:
    """Takes a prompt question and optionally a list of choices
     and returns the user input.

    Args:
        question: The question to ask the user.
        choices: A list of choices to select from.
        default: The default option selected.
        show_choices: Whether to show the choices.

    Returns:
        A string with the user input.
    """
    return Prompt.ask(
        question, choices=choices, default=default, show_choices=show_choices
    )  # type: ignore


def progress():
    """Create a new progress bar.


    Returns:
        A new progress bar.
    """
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
