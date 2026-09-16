"""Shared click options for the reflex CLIs."""

from __future__ import annotations

from typing import TYPE_CHECKING

import click
from reflex_base import constants
from reflex_base.utils import console, log

if TYPE_CHECKING:
    from collections.abc import Callable


def set_loglevel(ctx: click.Context, self: click.Parameter, value: str | None):
    """Set the log level.

    Args:
        ctx: The click context.
        self: The click command.
        value: The log level to set.
    """
    if value is not None:
        loglevel = constants.LogLevel.from_string(value)
        console.set_log_level(loglevel)


loglevel_option = click.option(
    "--loglevel",
    "--log-level",
    "loglevel",
    type=click.Choice(
        [loglevel.value for loglevel in constants.LogLevel],
        case_sensitive=False,
    ),
    is_eager=True,
    callback=set_loglevel,
    expose_value=False,
    help="The log level to use.",
)


def set_log_json(ctx: click.Context, self: click.Parameter, value: bool):
    """Enable machine-readable JSON log output.

    Args:
        ctx: The click context.
        self: The click command.
        value: Whether --json was passed.
    """
    if value:
        log.set_json_mode(True)


json_option = click.option(
    "--json",
    "log_json",
    is_flag=True,
    is_eager=True,
    callback=set_log_json,
    expose_value=False,
    help="Output logs as machine-readable JSON records.",
)


def log_options(func: Callable) -> Callable:
    """Apply the shared logging CLI options (--loglevel, --json).

    Args:
        func: The click command callback.

    Returns:
        The decorated callback.
    """
    return loglevel_option(json_option(func))
