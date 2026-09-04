"""Shared helpers for the hosting CLI tests."""

from __future__ import annotations

from typing import cast

import click
from typer import Typer
from typer.main import get_command


def as_click_command(cli: Typer | click.Command) -> click.Command:
    """Resolve the hosting CLI to a command that `CliRunner` can invoke.

    Args:
        cli: The hosting CLI, either wrapped in a Typer app or a plain click command.

    Returns:
        The click command to invoke.
    """
    if not isinstance(cli, Typer):
        return cli
    # typer >=0.27 vendors click, so its commands are structurally but not
    # nominally click commands.
    return cast("click.Command", get_command(cli))
