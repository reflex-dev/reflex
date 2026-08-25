"""Functions to communicate to the user via console (shared with reflex-base)."""

from __future__ import annotations

from reflex_base.constants.base import LogLevel
from reflex_base.utils import log as _log
from reflex_base.utils.console import PoorProgress as PoorProgress
from reflex_base.utils.console import ask as ask
from reflex_base.utils.console import debug as debug
from reflex_base.utils.console import deprecate as deprecate
from reflex_base.utils.console import error as error
from reflex_base.utils.console import info as info
from reflex_base.utils.console import is_debug as is_debug
from reflex_base.utils.console import log as log
from reflex_base.utils.console import print as print
from reflex_base.utils.console import print_table as print_table
from reflex_base.utils.console import progress as progress
from reflex_base.utils.console import rule as rule
from reflex_base.utils.console import set_log_level as _set_log_level
from reflex_base.utils.console import status as status
from reflex_base.utils.console import success as success
from reflex_base.utils.console import timing as timing
from reflex_base.utils.console import warn as warn


def set_log_level(log_level: LogLevel | str):
    """Set the log level, accepting legacy string values.

    Args:
        log_level: The log level to set.
    """
    if isinstance(log_level, str):
        log_level = LogLevel.from_string(log_level) or LogLevel.INFO
    _set_log_level(log_level)


def transfer_progress():
    """Create a progress bar measured in bytes rather than in steps.

    Lives here rather than beside ``progress`` in reflex-base because only the
    deploy upload wants it: a new name over there would raise this package's
    reflex-base floor, and the CLI is released on its own schedule.

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
        disable=_log.is_json_mode(),
    )
