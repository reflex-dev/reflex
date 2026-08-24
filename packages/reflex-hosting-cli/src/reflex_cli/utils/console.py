"""Interactive console helpers, shared with reflex-base when it is installed.

Level-gated messages go through :mod:`logging` (see :mod:`reflex_cli.utils.log`);
what remains here are the rich features that are output rather than logging:
prompts, tables, spinners and plain prints.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import overload

from reflex_cli.constants.base import LogLevel
from reflex_cli.utils.log import HAS_REFLEX_BASE
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


def set_log_level(log_level: LogLevel | str):
    """Set the log level, accepting legacy string values.

    Args:
        log_level: The log level to set.
    """
    if isinstance(log_level, str):
        log_level = LogLevel.from_string(log_level) or LogLevel.INFO
    _set_log_level(log_level)
