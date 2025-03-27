"""Functions to communicate to the user via console."""

from __future__ import annotations

import contextlib
import dataclasses
import inspect
import os
import re
import shutil
import sys
import time
import types
from dataclasses import dataclass
from pathlib import Path
from types import FrameType

from reflex.constants import LogLevel
from reflex.utils.terminal import colored


def _get_terminal_width() -> int:
    try:
        # First try using shutil, which is more reliable across platforms
        return shutil.get_terminal_size().columns
    except (AttributeError, ValueError, OSError):
        try:
            # Fallback to environment variables
            return int(os.environ.get("COLUMNS", os.environ.get("TERM_WIDTH", 80)))
        except (TypeError, ValueError):
            # Default fallback
            return 80


IS_REPRENTER_ACTIVE = False


@dataclasses.dataclass
class Reprinter:
    """A class that reprints text on the terminal."""

    _text: str = dataclasses.field(default="", init=False)

    @staticmethod
    def _moveup(lines: int):
        for _ in range(lines):
            sys.stdout.write("\x1b[A")

    @staticmethod
    def _movestart():
        sys.stdout.write("\r")

    def reprint(self, text: str):
        """Reprint the text.

        Args:
            text: The text to print
        """
        global IS_REPRENTER_ACTIVE
        IS_REPRENTER_ACTIVE = True
        text = text.rstrip("\n")
        number_of_lines = self._text.count("\n") + 1
        number_of_lines_new = text.count("\n") + 1

        # Clear previous text by overwritig non-spaces with spaces
        self._moveup(number_of_lines - 1)
        self._movestart()
        sys.stdout.write(re.sub(r"[^\s]", " ", self._text))

        # Print new text
        lines = min(number_of_lines, number_of_lines_new)
        self._moveup(lines - 1)
        self._movestart()
        sys.stdout.write(text)
        sys.stdout.flush()
        self._text = text

    def finish(self):
        """Finish printing the text."""
        sys.stdout.write("\n")
        sys.stdout.flush()
        global IS_REPRENTER_ACTIVE
        IS_REPRENTER_ACTIVE = False


STATUS_CHARS = ["◐", "◓", "◑", "◒"]


@dataclass
class Status:
    """A status class for displaying a spinner."""

    message: str = "Loading"
    _reprinter: Reprinter | None = dataclasses.field(default=None, init=False)
    _parity: int = dataclasses.field(default=0, init=False)

    def __enter__(self):
        """Enter the context manager.

        Returns:
            The status object.
        """
        self._reprinter = Reprinter()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: types.TracebackType | None,
    ):
        """Exit the context manager.

        Args:
            exc_type: The exception type.
            exc_value: The exception value.
            traceback: The traceback.
        """
        if self._reprinter:
            self._reprinter.reprint("")
            self._reprinter.finish()
            self._reprinter._moveup(1)
            sys.stdout.flush()
            self._reprinter = None

    def update(self, msg: str, **kwargs):
        """Update the status spinner.

        Args:
            msg: The message to display.
            kwargs: Keyword arguments to pass to the print function.
        """
        if self._reprinter:
            char = STATUS_CHARS[self._parity % 4]
            self._parity += 1
            self._reprinter.reprint(f"{char} {msg}")


@dataclass
class Console:
    """A console class for pretty printing."""

    def print(self, msg: str, **kwargs):
        """Print a message.

        Args:
            msg: The message to print.
            kwargs: Keyword arguments to pass to the print function.
        """
        from builtins import print

        color = kwargs.pop("color", None)
        bold = kwargs.pop("bold", False)
        if color or bold:
            msg = colored(msg, color, attrs=["bold"] if bold else [])

        if IS_REPRENTER_ACTIVE:
            print("\n" + msg, flush=True, **kwargs)  # noqa: T201
        else:
            print(msg, **kwargs)  # noqa: T201

    def rule(self, title: str, **kwargs):
        """Prints a horizontal rule with a title.

        Args:
            title: The title of the rule.
            kwargs: Keyword arguments to pass to the print function.
        """
        terminal_width = _get_terminal_width()
        remaining_width = (
            terminal_width - len(title) - 2
        )  # 2 for the spaces around the title
        left_padding = remaining_width // 2
        right_padding = remaining_width - left_padding

        color = kwargs.pop("color", None)
        bold = kwargs.pop("bold", True)
        rule_color = "green" if color is None else color
        title = colored(title, color, attrs=("bold",) if bold else ())

        rule_line = (
            colored("─" * left_padding, rule_color)
            + " "
            + title
            + " "
            + colored("─" * right_padding, rule_color)
        )
        self.print(rule_line, **kwargs)

    def status(self, *args, **kwargs):
        """Create a status.

        Args:
            *args: Args to pass to the status.
            **kwargs: Kwargs to pass to the status.

        Returns:
            A new status.
        """
        return Status(*args, **kwargs)


class Prompt:
    """A class for prompting the user for input."""

    @staticmethod
    def ask(
        question: str,
        choices: list[str] | None = None,
        default: str | None = None,
        show_choices: bool = True,
    ) -> str | None:
        """Ask the user a question.

        Args:
            question: The question to ask the user.
            choices: A list of choices to select from.
            default: The default option selected.
            show_choices: Whether to show the choices.

        Returns:
            The user's response or the default value.
        """
        prompt = question

        if choices and show_choices:
            choice_str = "/".join(choices)
            prompt = f"{question} [{choice_str}]"

        if default is not None:
            prompt = f"{prompt} ({default})"

        prompt = f"{prompt}: "

        response = input(prompt)

        if not response and default is not None:
            return default

        if choices and response not in choices:
            print(f"Please choose from: {', '.join(choices)}")
            return Prompt.ask(question, choices, default, show_choices)

        return response


# Console for pretty printing.
_console = Console()

# The current log level.
_LOG_LEVEL = LogLevel.INFO

# Deprecated features who's warning has been printed.
_EMITTED_DEPRECATION_WARNINGS = set()

# Info messages which have been printed.
_EMITTED_INFO = set()

# Warnings which have been printed.
_EMIITED_WARNINGS = set()

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


def set_log_level(log_level: LogLevel):
    """Set the log level.

    Args:
        log_level: The log level to set.

    Raises:
        TypeError: If the log level is a string.
    """
    if not isinstance(log_level, LogLevel):
        raise TypeError(
            f"log_level must be a LogLevel enum value, got {log_level} of type {type(log_level)} instead."
        )
    global _LOG_LEVEL
    if log_level != _LOG_LEVEL:
        # Set the loglevel persistenly for subprocesses.
        os.environ["LOGLEVEL"] = log_level.value
    _LOG_LEVEL = log_level


def is_debug() -> bool:
    """Check if the log level is debug.

    Returns:
        True if the log level is debug.
    """
    return _LOG_LEVEL <= LogLevel.DEBUG


def print(msg: str, dedupe: bool = False, **kwargs):
    """Print a message.

    Args:
        msg: The message to print.
        dedupe: If True, suppress multiple console logs of print message.
        kwargs: Keyword arguments to pass to the print function.
    """
    if dedupe:
        if msg in _EMITTED_PRINTS:
            return
        else:
            _EMITTED_PRINTS.add(msg)
    _console.print(msg, **kwargs)


def debug(msg: str, dedupe: bool = False, **kwargs):
    """Print a debug message.

    Args:
        msg: The debug message.
        dedupe: If True, suppress multiple console logs of debug message.
        kwargs: Keyword arguments to pass to the print function.
    """
    if is_debug():
        if dedupe:
            if msg in _EMITTED_DEBUG:
                return
            else:
                _EMITTED_DEBUG.add(msg)
        kwargs.setdefault("color", "debug")
        print(msg, **kwargs)


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
        kwargs.setdefault("color", "info")
        print(f"Info: {msg}", **kwargs)


def success(msg: str, dedupe: bool = False, **kwargs):
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
            else:
                _EMITTED_SUCCESS.add(msg)
        kwargs.setdefault("color", "success")
        print(f"Success: {msg}", **kwargs)


def log(msg: str, dedupe: bool = False, **kwargs):
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
            else:
                _EMITTED_LOGS.add(msg)
        _console.print(msg, **kwargs)


def rule(title: str, **kwargs):
    """Prints a horizontal rule with a title.

    Args:
        title: The title of the rule.
        kwargs: Keyword arguments to pass to the print function.
    """
    _console.rule(title, **kwargs)


def warn(msg: str, dedupe: bool = False, **kwargs):
    """Print a warning message.

    Args:
        msg: The warning message.
        dedupe: If True, suppress multiple console logs of warning message.
        kwargs: Keyword arguments to pass to the print function.
    """
    if _LOG_LEVEL <= LogLevel.WARNING:
        if dedupe:
            if msg in _EMIITED_WARNINGS:
                return
            else:
                _EMIITED_WARNINGS.add(msg)
        kwargs.setdefault("color", "warning")
        print(f"Warning: {msg}", **kwargs)


def _get_first_non_framework_frame() -> FrameType | None:
    import click
    import typer
    import typing_extensions

    import reflex as rx

    # Exclude utility modules that should never be the source of deprecated reflex usage.
    exclude_modules = [click, rx, typer, typing_extensions]
    exclude_roots = [
        p.parent.resolve()
        if (p := Path(m.__file__)).name == "__init__.py"  # pyright: ignore [reportArgumentType]
        else p.resolve()
        for m in exclude_modules
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
            kwargs.setdefault("color", "warning")
            print(f"DeprecationWarning: {msg}", **kwargs)
        if dedupe:
            _EMITTED_DEPRECATION_WARNINGS.add(dedupe_key)


def error(msg: str, dedupe: bool = False, **kwargs):
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
            else:
                _EMITTED_ERRORS.add(msg)
        kwargs.setdefault("color", "error")
        print(f"{msg}", **kwargs)


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
    start = time.monotonic()
    try:
        yield
    finally:
        debug(f"[timing] {msg}: {time.monotonic() - start:.2f}s", color="white")
