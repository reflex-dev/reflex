"""Reflex utilities."""

import click

from reflex_cli.constants.hosting import ReflexHostingCli

from . import console


def disabled_v1_hosting(*args, **kwargs):
    """Print error and exit when using v1 hosting commands.

    Args:
        *args: ignored.
        **kwargs: ignored.

    Raises:
        Exit: Always.

    """
    console.error(
        "The alpha hosting service has been decommissioned as of Dec 5, 2024. "
        f"Please upgrade to reflex>={ReflexHostingCli.MINIMUM_REFLEX_VERSION} to use Reflex Cloud hosting."
    )
    raise click.exceptions.Exit(1)
