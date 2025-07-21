"""Functions to communicate to the user via console."""

from __future__ import annotations

import contextlib
import inspect
import os
import shutil
import time
from pathlib import Path
from types import FrameType

from rich.console import Console
from rich.progress import MofNCompleteColumn, Progress, TimeElapsedColumn
from rich.prompt import Prompt

from reflex.constants import LogLevel
from reflex.constants.base import Reflex
from reflex.utils.decorator import once

# Console for pretty printing.
_console = Console()

# The current log level.
_LOG_LEVEL = LogLevel.INFO

# Deprecated features who's warning has been printed.
_EMITTED_DEPRECATION_WARNINGS = set()

# Info messages which have been printed.
_EMITTED_INFO = set()

# Warnings which have been printed.
_EMITTED_WARNINGS = set()

# Errors which have been printed.
_EMITTED_ERRORS = set()

# Success messages which have been printed.
_EMITTED_SUCCESS = set()

# Debug messages which have been printed.
_EMITTED_DEBUG = set()

# Logs which have been printed.
_EMITTED_LOGS = set()

# Prints which have been printed.
_EMITTED_PRINTS = set()


def set_log_level(log_level: LogLevel | None):
    """Set the log level.

    Args:
        log_level: The log level to set.

    Raises:
        TypeError: If the log level is a string.
    """
    if log_level is None:
        return
    if not isinstance(log_level, LogLevel):
        msg = f"log_level must be a LogLevel enum value, got {log_level} of type {type(log_level)} instead."
        raise TypeError(msg)
    global _LOG_LEVEL
    if log_level != _LOG_LEVEL:
        # Set the loglevel persistenly for subprocesses.
        os.environ["REFLEX_LOGLEVEL"] = log_level.value
    _LOG_LEVEL = log_level


def is_debug() -> bool:
    """Check if the log level is debug.

    Returns:
        True if the log level is debug.
    """
    return _LOG_LEVEL <= LogLevel.DEBUG


def print(msg: str, *, dedupe: bool = False, **kwargs):
    """Print a message.

    Args:
        msg: The message to print.
        dedupe: If True, suppress multiple console logs of print message.
        kwargs: Keyword arguments to pass to the print function.
    """
    if dedupe:
        if msg in _EMITTED_PRINTS:
            return
        _EMITTED_PRINTS.add(msg)
    _console.print(msg, **kwargs)


@once
def log_file_console():
    """Create a console that logs to a file.

    Returns:
        A Console object that logs to a file.
    """
    from reflex.environment import environment

    if not (env_log_file := environment.REFLEX_LOG_FILE.get()):
        subseconds = int((time.time() % 1) * 1000)
        timestamp = time.strftime("%Y-%m-%d_%H-%M-%S") + f"_{subseconds:03d}"
        log_file = Reflex.DIR / "logs" / (timestamp + ".log")
        log_file.parent.mkdir(parents=True, exist_ok=True)
    else:
        log_file = env_log_file
    if log_file.exists():
        log_file.unlink()
    log_file.touch()
    return Console(file=log_file.open("a", encoding="utf-8"))


@once
def should_use_log_file_console() -> bool:
    """Check if the log file console should be used.

    Returns:
        True if the log file console should be used, False otherwise.
    """
    from reflex.environment import environment

    return environment.REFLEX_ENABLE_FULL_LOGGING.get()


def print_to_log_file(msg: str, *, dedupe: bool = False, **kwargs):
    """Print a message to the log file.

    Args:
        msg: The message to print.
        dedupe: If True, suppress multiple console logs of print message.
        kwargs: Keyword arguments to pass to the print function.
    """
    log_file_console().print(msg, **kwargs)


def debug(msg: str, *, dedupe: bool = False, **kwargs):
    """Print a debug message.

    Args:
        msg: The debug message.
        dedupe: If True, suppress multiple console logs of debug message.
        kwargs: Keyword arguments to pass to the print function.
    """
    if is_debug():
        msg_ = f"[purple]Debug: {msg}[/purple]"
        if dedupe:
            if msg_ in _EMITTED_DEBUG:
                return
            _EMITTED_DEBUG.add(msg_)
        if progress := kwargs.pop("progress", None):
            progress.console.print(msg_, **kwargs)
        else:
            print(msg_, **kwargs)
    if should_use_log_file_console() and kwargs.pop("progress", None) is None:
        print_to_log_file(f"[purple]Debug: {msg}[/purple]", **kwargs)


def info(msg: str, *, dedupe: bool = False, **kwargs):
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
            _EMITTED_INFO.add(msg)
        print(f"[cyan]Info: {msg}[/cyan]", **kwargs)
    if should_use_log_file_console():
        print_to_log_file(f"[cyan]Info: {msg}[/cyan]", **kwargs)


def success(msg: str, *, dedupe: bool = False, **kwargs):
    """Print a success message.

    Args:
        msg: The success message.
        dedupe: If True, suppress multiple console logs of success message.
        kwargs: Keyword arguments to pass to the print function.
    """
    if _LOG_LEVEL <= LogLevel.INFO:
        if dedupe:
            if msg in _EMITTED_SUCCESS:
                return
            _EMITTED_SUCCESS.add(msg)
        print(f"[green]Success: {msg}[/green]", **kwargs)
    if should_use_log_file_console():
        print_to_log_file(f"[green]Success: {msg}[/green]", **kwargs)


def log(msg: str, *, dedupe: bool = False, **kwargs):
    """Takes a string and logs it to the console.

    Args:
        msg: The message to log.
        dedupe: If True, suppress multiple console logs of log message.
        kwargs: Keyword arguments to pass to the print function.
    """
    if _LOG_LEVEL <= LogLevel.INFO:
        if dedupe:
            if msg in _EMITTED_LOGS:
                return
            _EMITTED_LOGS.add(msg)
        _console.log(msg, **kwargs)
    if should_use_log_file_console():
        print_to_log_file(msg, **kwargs)


def rule(title: str, **kwargs):
    """Prints a horizontal rule with a title.

    Args:
        title: The title of the rule.
        kwargs: Keyword arguments to pass to the print function.
    """
    _console.rule(title, **kwargs)


def warn(msg: str, *, dedupe: bool = False, **kwargs):
    """Print a warning message.

    Args:
        msg: The warning message.
        dedupe: If True, suppress multiple console logs of warning message.
        kwargs: Keyword arguments to pass to the print function.
    """
    if _LOG_LEVEL <= LogLevel.WARNING:
        if dedupe:
            if msg in _EMITTED_WARNINGS:
                return
            _EMITTED_WARNINGS.add(msg)
        print(f"[orange1]Warning: {msg}[/orange1]", **kwargs)
    if should_use_log_file_console():
        print_to_log_file(f"[orange1]Warning: {msg}[/orange1]", **kwargs)


def _get_first_non_framework_frame() -> FrameType | None:
    import click
    import typing_extensions

    import reflex as rx

    # Exclude utility modules that should never be the source of deprecated reflex usage.
    exclude_modules = [click, rx, typing_extensions]
    exclude_roots = [
        p.parent.resolve() if (p := Path(file)).name == "__init__.py" else p.resolve()
        for m in exclude_modules
        if (file := m.__file__)
    ]
    # Specifically exclude the reflex cli module.
    if reflex_bin := shutil.which(b"reflex"):
        exclude_roots.append(Path(reflex_bin.decode()))

    frame = inspect.currentframe()
    while frame := frame and frame.f_back:
        frame_path = Path(inspect.getfile(frame)).resolve()
        if not any(frame_path.is_relative_to(root) for root in exclude_roots):
            break
    return frame


def deprecate(
    *,
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
    dedupe_key = feature_name
    loc = ""

    # See if we can find where the deprecation exists in "user code"
    origin_frame = _get_first_non_framework_frame()
    if origin_frame is not None:
        filename = Path(origin_frame.f_code.co_filename)
        if filename.is_relative_to(Path.cwd()):
            filename = filename.relative_to(Path.cwd())
        loc = f"{filename}:{origin_frame.f_lineno}"
        dedupe_key = f"{dedupe_key} {loc}"

    if dedupe_key not in _EMITTED_DEPRECATION_WARNINGS:
        msg = (
            f"{feature_name} has been deprecated in version {deprecation_version}. {reason.rstrip('.').lstrip('. ')}. It will be completely "
            f"removed in {removal_version}. ({loc})"
        )
        if _LOG_LEVEL <= LogLevel.WARNING:
            print(f"[yellow]DeprecationWarning: {msg}[/yellow]", **kwargs)
        if should_use_log_file_console():
            print_to_log_file(f"[yellow]DeprecationWarning: {msg}[/yellow]", **kwargs)
        if dedupe:
            _EMITTED_DEPRECATION_WARNINGS.add(dedupe_key)


def error(msg: str, *, dedupe: bool = False, **kwargs):
    """Print an error message.

    Args:
        msg: The error message.
        dedupe: If True, suppress multiple console logs of error message.
        kwargs: Keyword arguments to pass to the print function.
    """
    if _LOG_LEVEL <= LogLevel.ERROR:
        if dedupe:
            if msg in _EMITTED_ERRORS:
                return
            _EMITTED_ERRORS.add(msg)
        print(f"[red]{msg}[/red]", **kwargs)
    if should_use_log_file_console():
        print_to_log_file(f"[red]{msg}[/red]", **kwargs)


def ask(
    question: str,
    choices: list[str] | None = None,
    default: str | None = None,
    show_choices: bool = True,
) -> str | None:
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
    )


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


@contextlib.contextmanager
def timing(msg: str):
    """Create a context manager to time a block of code.

    Args:
        msg: The message to display.

    Yields:
        None.
    """
    start = time.time()
    try:
        yield
    finally:
        debug(f"[white]\\[timing] {msg}: {time.time() - start:.2f}s[/white]")
