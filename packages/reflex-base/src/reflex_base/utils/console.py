"""Functions to communicate to the user via console.

The logging-shaped helpers (``debug``/``info``/``success``/``log``/``warn``/
``error``/``timing``) are deprecated and kept with their legacy behavior until
removal; new code should use ``logging.getLogger(__name__)`` and the pipeline
in :mod:`reflex_base.utils.log`. The interactive Rich features
(``print``/``rule``/``status``/``ask``/``progress``) remain first-class.
"""

from __future__ import annotations

import contextlib
import datetime
import functools
import inspect
import shutil
import sys
import time
from collections.abc import Sequence
from pathlib import Path
from types import FrameType, ModuleType
from typing import TYPE_CHECKING, overload

from rich.console import Console, OverflowMethod
from rich.progress import MofNCompleteColumn, Progress, TaskID, TimeElapsedColumn
from rich.prompt import Prompt
from rich.table import Table

from reflex_base.constants import LogLevel
from reflex_base.utils import log as _log
from reflex_base.utils.decorator import once

# Console for pretty printing.
_console = Console(highlight=False)
_console_stderr = Console(stderr=True, highlight=False)

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


def _shim_deprecation(name: str, replacement: str):
    """Warn that a deprecated console logging helper was called.

    Args:
        name: The console function name.
        replacement: The logging-API replacement to suggest.
    """
    deprecate(
        feature_name=f"console.{name}",
        reason=f"use {replacement} on logging.getLogger(__name__) instead",
        deprecation_version="0.9.9",
        removal_version="1.0",
    )


def set_log_level(log_level: LogLevel | None):
    """Set the log level.

    Args:
        log_level: The log level to set.
    """
    _log.set_log_level(log_level)


def is_debug() -> bool:
    """Check if the log level is debug.

    Returns:
        True if the log level is debug.
    """
    return _log.is_debug()


def print(msg: str, *, dedupe: bool = False, level: str = "info", **kwargs):
    """Print a message.

    Args:
        msg: The message to print.
        dedupe: If True, suppress multiple console logs of print message.
        level: The severity reported in JSON mode.
        kwargs: Keyword arguments to pass to the print function.
    """
    if _log.is_json_mode():
        _log.emit_json_print(msg, level=level, dedupe=dedupe)
        return
    if dedupe:
        if msg in _EMITTED_PRINTS:
            return
        _EMITTED_PRINTS.add(msg)
    _console.print(msg, **kwargs)


def _print_stderr(msg: str, *, dedupe: bool = False, level: str = "error", **kwargs):
    """Print a message to stderr.

    Args:
        msg: The message to print.
        dedupe: If True, suppress multiple console logs of print message.
        level: The severity reported in JSON mode.
        kwargs: Keyword arguments to pass to the print function.
    """
    if _log.is_json_mode():
        _log.emit_json_print(msg, level=level, dedupe=dedupe, stderr=True)
        return
    if dedupe:
        if msg in _EMITTED_PRINTS:
            return
        _EMITTED_PRINTS.add(msg)
    _console_stderr.print(msg, **kwargs)


@once
def log_file_console():
    """Create a console that logs to a file.

    Writes through a proxy to the logging pipeline's file-handler stream, so
    the legacy helpers and the ``logging`` sinks share one full-logging file
    even after an external logging re-config closes and reopens the handler.

    Returns:
        A Console object that logs to a file.
    """
    return Console(file=_log.log_file_proxy())


@once
def should_use_log_file_console() -> bool:
    """Check if the log file console should be used.

    Returns:
        True if the log file console should be used, False otherwise.
    """
    from reflex_base.environment import environment

    return environment.REFLEX_ENABLE_FULL_LOGGING.get()


def print_to_log_file(msg: str, *, dedupe: bool = False, **kwargs):
    """Print a message to the log file.

    Args:
        msg: The message to print.
        dedupe: If True, suppress multiple console logs of print message.
        kwargs: Keyword arguments to pass to the print function.
    """
    log_file_console().print(f"[{datetime.datetime.now()}] {msg}", **kwargs)


def _debug(msg: str, *, dedupe: bool = False, **kwargs):
    """Render a debug message with the legacy behavior."""
    if is_debug():
        msg_ = f"[purple]Debug: {msg}[/purple]"
        if dedupe:
            if msg_ in _EMITTED_DEBUG:
                return
            _EMITTED_DEBUG.add(msg_)
        if progress := kwargs.pop("progress", None):
            progress.console.print(msg_, **kwargs)
        else:
            print(msg_, level="debug", **kwargs)
    if should_use_log_file_console() and kwargs.pop("progress", None) is None:
        print_to_log_file(f"[purple]Debug: {msg}[/purple]", **kwargs)


def debug(msg: str, *, dedupe: bool = False, **kwargs):
    """Print a debug message.

    Args:
        msg: The debug message.
        dedupe: If True, suppress multiple console logs of debug message.
        kwargs: Keyword arguments to pass to the print function.
    """
    _shim_deprecation("debug", "logger.debug(msg)")
    _debug(msg, dedupe=dedupe, **kwargs)


def info(msg: str, *, dedupe: bool = False, **kwargs):
    """Print an info message.

    Args:
        msg: The info message.
        dedupe: If True, suppress multiple console logs of info message.
        kwargs: Keyword arguments to pass to the print function.
    """
    _shim_deprecation("info", "logger.info(msg)")
    if _log.get_log_level() <= LogLevel.INFO:
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
    _shim_deprecation("success", "logger.log(log.SUCCESS, msg)")
    if _log.get_log_level() <= LogLevel.INFO:
        if dedupe:
            if msg in _EMITTED_SUCCESS:
                return
            _EMITTED_SUCCESS.add(msg)
        print(f"[green]Success: {msg}[/green]", level="success", **kwargs)
    if should_use_log_file_console():
        print_to_log_file(f"[green]Success: {msg}[/green]", **kwargs)


def log(msg: str, *, dedupe: bool = False, **kwargs):
    """Takes a string and logs it to the console.

    Args:
        msg: The message to log.
        dedupe: If True, suppress multiple console logs of log message.
        kwargs: Keyword arguments to pass to the print function.
    """
    _shim_deprecation("log", "logger.info(msg)")
    if _log.get_log_level() <= LogLevel.INFO:
        if dedupe:
            if msg in _EMITTED_LOGS:
                return
            _EMITTED_LOGS.add(msg)
        if _log.is_json_mode():
            _log.emit_json_print(msg)
        else:
            _console.log(msg, **kwargs)
    if should_use_log_file_console():
        print_to_log_file(msg, **kwargs)


def rule(title: str, **kwargs):
    """Prints a horizontal rule with a title.

    Args:
        title: The title of the rule.
        kwargs: Keyword arguments to pass to the print function.
    """
    if _log.is_json_mode():
        return
    _console.rule(title, **kwargs)


def warn(msg: str, *, dedupe: bool = False, **kwargs):
    """Print a warning message.

    Args:
        msg: The warning message.
        dedupe: If True, suppress multiple console logs of warning message.
        kwargs: Keyword arguments to pass to the print function.
    """
    _shim_deprecation("warn", "logger.warning(msg)")
    if _log.get_log_level() <= LogLevel.WARNING:
        if dedupe:
            if msg in _EMITTED_WARNINGS:
                return
            _EMITTED_WARNINGS.add(msg)
        print(f"[orange1]Warning: {msg}[/orange1]", level="warning", **kwargs)
    if should_use_log_file_console():
        print_to_log_file(f"[orange1]Warning: {msg}[/orange1]", **kwargs)


@once
def _exclude_paths_from_frame_info() -> list[Path]:
    import importlib.util

    import click
    import granian
    import socketio
    import typing_extensions

    import reflex_base

    try:
        import reflex as rx
    except ImportError:
        rx = None

    # Exclude utility modules that should never be the source of deprecated reflex usage.
    exclude_modules: list[ModuleType | None] = [
        click,
        rx,
        typing_extensions,
        socketio,
        granian,
        reflex_base,
    ]

    modules_paths = [file for m in exclude_modules if m and (file := m.__file__)] + [
        spec.origin
        for m in [*sys.builtin_module_names, *sys.stdlib_module_names]
        if (spec := importlib.util.find_spec(m)) and spec.origin
    ]
    exclude_roots = [
        p.parent.resolve() if (p := Path(file)).name == "__init__.py" else p.resolve()
        for file in modules_paths
    ]
    # Specifically exclude the reflex cli module.
    if reflex_bin := shutil.which(b"reflex"):
        exclude_roots.append(Path(reflex_bin.decode()))

    return exclude_roots


@functools.cache
def _is_framework_filename(filename: str) -> bool:
    """Check if a code filename belongs to an excluded framework/stdlib root.

    Cached per filename: module file locations do not move within a process,
    but resolving a path and comparing it against every exclude root is far
    too expensive to repeat for each frame on every deprecation check.

    Args:
        filename: The ``co_filename`` of a frame's code object.

    Returns:
        Whether the file lives under one of the excluded framework roots.
    """
    frame_path = Path(filename).resolve()
    return any(
        frame_path.is_relative_to(root) for root in _exclude_paths_from_frame_info()
    )


def _get_first_non_framework_frame() -> FrameType | None:
    frame = inspect.currentframe()
    while frame := frame and frame.f_back:
        if not _is_framework_filename(frame.f_code.co_filename):
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
        loc = f" ({filename}:{origin_frame.f_lineno})"
        dedupe_key = f"{dedupe_key} {loc}"

    if dedupe_key not in _EMITTED_DEPRECATION_WARNINGS:
        msg = (
            f"{feature_name} has been deprecated in version {deprecation_version}. {reason.rstrip('.').lstrip('. ')}. It will be completely "
            f"removed in {removal_version}.{loc}"
        )
        if _log.get_log_level() <= LogLevel.WARNING:
            print(
                f"[yellow]DeprecationWarning: {msg}[/yellow]",
                level="warning",
                **kwargs,
            )
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
    _shim_deprecation("error", "logger.error(msg)")
    if _log.get_log_level() <= LogLevel.ERROR:
        if dedupe:
            if msg in _EMITTED_ERRORS:
                return
            _EMITTED_ERRORS.add(msg)
        _print_stderr(f"[red]{msg}[/red]", **kwargs)
    if should_use_log_file_console():
        print_to_log_file(f"[red]{msg}[/red]", **kwargs)


@overload
def ask(
    question: str,
    choices: list[str] | None = None,
    *,
    show_choices: bool = True,
) -> str: ...


@overload
def ask(
    question: str,
    choices: list[str] | None = None,
    default: str = ...,
    show_choices: bool = True,
) -> str: ...


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


def print_table(
    tabular_data: list[list[str]],
    headers: Sequence[str] = (),
    overflow: OverflowMethod = "ellipsis",
) -> None:
    """Print a table to the console.

    Args:
        tabular_data: The data to print in tabular format.
        headers: The headers for the table.
        overflow: What to do with a cell too wide for its column. The default
            cuts it short; pass "fold" for values a user has to read in full,
            such as an email or an identifier.
    """
    if _log.is_json_mode():
        # A table is requested output, not decoration: keep the rows in the
        # machine-readable stream instead of rendering Rich text into it.
        _log.emit_json_print(
            "",
            table={"headers": list(headers), "rows": tabular_data},
        )
        return
    table = Table()

    for column in headers:
        table.add_column(column, overflow=overflow)

    for row in tabular_data:
        table.add_row(*row)

    _console.print(table)


def progress():
    """Create a new progress bar.

    Returns:
        A new progress bar.
    """
    return Progress(
        *Progress.get_default_columns()[:-1],
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        disable=_log.is_json_mode(),
    )


def status(*args, **kwargs):
    """Create a status with a spinner.

    Args:
        *args: Args to pass to the status.
        **kwargs: Kwargs to pass to the status.

    Returns:
        A new status.
    """
    if _log.is_json_mode():
        return _log._quiet_console.status(*args, **kwargs)
    return _console.status(*args, **kwargs)


@contextlib.contextmanager
def timing(msg: str):
    """Create a context manager to time a block of code.

    Args:
        msg: The message to display.

    Yields:
        None.
    """
    _shim_deprecation("timing", "log.timing(logger, msg)")
    start = time.time()
    try:
        yield
    finally:
        _debug(f"[white]\\[timing] {msg}: {time.time() - start:.2f}s[/white]")


class PoorProgress:
    """A poor man's progress bar."""

    def __init__(self):
        """Initialize the progress bar."""
        super().__init__()
        self.tasks = {}
        self.progress = 0
        self.total = 0

    def add_task(self, task: str, total: int):
        """Add a task to the progress bar.

        Args:
            task: The task name.
            total: The total number of steps for the task.

        Returns:
            The task ID.
        """
        self.total += total
        task_id = TaskID(len(self.tasks))
        self.tasks[task_id] = {"total": total, "current": 0}
        return task_id

    def advance(self, task: TaskID, advance: int = 1):
        """Advance the progress of a task.

        Args:
            task: The task ID.
            advance: The number of steps to advance.
        """
        if task in self.tasks:
            self.tasks[task]["current"] += advance
            self.progress += advance
            # Through console.print, so JSON mode gets a record instead of a
            # plain line in the machine-readable stream.
            print(f"Progress: {self.progress}/{self.total}")

    def update(self, task: TaskID, total: int | None = None):
        """Update properties of a task.

        Args:
            task: The task ID.
            total: New total for the task.
        """
        if total is not None and task in self.tasks:
            previous_total = self.tasks[task]["total"]
            self.tasks[task]["total"] = total
            self.total += total - previous_total

    def start(self):
        """Start the progress bar."""

    def stop(self):
        """Stop the progress bar."""


if TYPE_CHECKING:
    from typing_extensions import deprecated

    debug = deprecated("Use logging.getLogger(__name__).debug(msg) instead")(debug)
    info = deprecated("Use logging.getLogger(__name__).info(msg) instead")(info)
    success = deprecated(
        "Use logging.getLogger(__name__).log(log.SUCCESS, msg) instead"
    )(success)
    log = deprecated("Use logging.getLogger(__name__).info(msg) instead")(log)
    warn = deprecated("Use logging.getLogger(__name__).warning(msg) instead")(warn)
    error = deprecated("Use logging.getLogger(__name__).error(msg) instead")(error)
    timing = deprecated("Use reflex_base.utils.log.timing(logger, msg) instead")(timing)
