"""Interactive console helpers, shared with reflex-base when it is installed.

Level-gated messages go through :mod:`logging` (see :mod:`reflex_cli.utils.log`);
what remains here are the rich features that are output rather than logging:
prompts, tables, spinners and plain prints.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import overload

from reflex_cli.constants.base import LogLevel
from reflex_cli.utils.log import HAS_REFLEX_BASE, is_json_mode
from reflex_cli.utils.log import set_log_level as _set_log_level

if HAS_REFLEX_BASE:
    from reflex_base.utils.console import ask as ask
    from reflex_base.utils.console import print as print
    from reflex_base.utils.console import print_table as print_table
    from reflex_base.utils.console import progress as progress
    from reflex_base.utils.console import rule as rule
    from reflex_base.utils.console import status as status
else:
    from rich.console import Console, OverflowMethod
    from rich.progress import MofNCompleteColumn, Progress, TimeElapsedColumn
    from rich.prompt import Prompt
    from rich.table import Table

    _console = Console(highlight=False)

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
        overflow: OverflowMethod = "ellipsis",
    ) -> None:
        """Print a table to the console.

        Args:
            tabular_data: The data to print in tabular format.
            headers: The headers for the table.
            overflow: What to do with a cell too wide for its column. The
                default cuts it short; pass "fold" for values a user has to
                read in full, such as an email or an identifier.
        """
        table = Table()

        for column in headers:
            table.add_column(column, overflow=overflow)

        for row in tabular_data:
            table.add_row(*row)

        _console.print(table)

    def rule(title: str, **kwargs):
        """Print a horizontal rule with a title.

        Args:
            title: The title of the rule.
            kwargs: Keyword arguments to pass to the print function.
        """
        _console.rule(title, **kwargs)

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
        """Ask the user a question, optionally with a list of choices.

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


def set_log_level(log_level: LogLevel | str | None):
    """Set the log level, accepting legacy string values and foreign enums.

    Older reflex releases call the CLI's entrypoints directly rather than
    through click, handing over their own ``reflex.constants.LogLevel``. That is
    a different class from this package's -- and, before the enum grew
    ``to_logging_level``, one the CLI cannot use -- so it is resolved by value,
    the way a legacy plain string is. An unrecognized value falls back to INFO.

    Args:
        log_level: The log level to set, or None to leave it unchanged.
    """
    if log_level is not None and not isinstance(log_level, LogLevel):
        # A foreign LogLevel carries the level in ``value``; a plain string is
        # already the value. Either way it resolves by name.
        log_level = (
            LogLevel.from_string(getattr(log_level, "value", log_level))
            or LogLevel.INFO
        )
    _set_log_level(log_level)


def transfer_progress():
    """Create a progress bar measured in bytes rather than in steps.

    Lives here rather than beside ``progress`` in reflex-base because only the
    deploy upload wants it, and the CLI has to render it whether or not
    reflex-base is installed.

    Returns:
        A new progress bar, sized and paced for a file transfer.
    """
    from rich.progress import (
        BarColumn,
        DownloadColumn,
        Progress,
        TextColumn,
        TimeElapsedColumn,
        TransferSpeedColumn,
    )

    return Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        DownloadColumn(),
        TransferSpeedColumn(),
        TimeElapsedColumn(),
        disable=is_json_mode(),
    )
