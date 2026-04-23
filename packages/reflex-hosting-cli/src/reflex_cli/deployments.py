"""Disabled Hosting CLI deployments sub-commands."""

from __future__ import annotations

from importlib.util import find_spec
from typing import TYPE_CHECKING

import click

from reflex_cli import constants
from reflex_cli.utils import disabled_v1_hosting

if TYPE_CHECKING:
    import typer


TIME_FORMAT_HELP = "Accepts ISO 8601 format, unix epoch or time relative to now. For time relative to now, use the format: <d><unit>. Valid units are d (day), h (hour), m (minute), s (second). For example, 1d for 1 day ago from now."
MIN_LOGS_LIMIT = 50
MAX_LOGS_LIMIT = 1000


@click.group()
def deployments_cli():
    """Commands for managing deployments."""
    disabled_v1_hosting()


@deployments_cli.command(name="list")
@click.option(
    "--loglevel",
    type=click.Choice([level.value for level in constants.LogLevel]),
    default=constants.LogLevel.INFO.value,
    help="The log level to use.",
)
@click.option(
    "--json/--no-json",
    "-j",
    "as_json",
    is_flag=True,
    help="Whether to output the result in json format.",
)
def list_deployments(loglevel: str, as_json: bool):
    """List all the hosted deployments of the authenticated user.

    Args:
        loglevel: The log level to use.
        as_json: Whether to output the result in json format.

    """


@deployments_cli.command(name="delete")
@click.argument("key", required=True)
@click.option(
    "--loglevel",
    type=click.Choice([level.value for level in constants.LogLevel]),
    default=constants.LogLevel.INFO.value,
    help="The log level to use.",
)
def delete_deployment(key: str, loglevel: str):
    """Delete a hosted instance.

    Args:
        key: The name of the deployment.
        loglevel: The log level to use.

    """


@deployments_cli.command(name="status")
@click.argument("key", required=True)
@click.option(
    "--loglevel",
    type=click.Choice([level.value for level in constants.LogLevel]),
    default=constants.LogLevel.INFO.value,
    help="The log level to use.",
)
def get_deployment_status(key: str, loglevel: str):
    """Check the status of a deployment.

    Args:
        key: The name of the deployment.
        loglevel: The log level to use.

    """


@deployments_cli.command(name="logs")
@click.argument("key", required=True)
@click.option(
    "--from", "from_timestamp", help=f"The start time of the logs. {TIME_FORMAT_HELP}"
)
@click.option(
    "--to", "to_timestamp", help=f"The end time of the logs. {TIME_FORMAT_HELP}"
)
@click.option(
    "--limit",
    type=int,
    help=f"The number of logs to return. The acceptable range is {MIN_LOGS_LIMIT}-{MAX_LOGS_LIMIT}.",
)
@click.option(
    "--loglevel",
    type=click.Choice([level.value for level in constants.LogLevel]),
    default=constants.LogLevel.INFO.value,
    help="The log level to use.",
)
def get_deployment_logs(
    key: str,
    from_timestamp: str | None,
    to_timestamp: str | None,
    limit: int | None,
    loglevel: str,
):
    """Get the logs for a deployment.

    Args:
        key: The name of the deployment.
        from_timestamp: The start time of the logs.
        to_timestamp: The end time of the logs.
        limit: The maximum number of logs to return.
        loglevel: The log level to use.

    """


@deployments_cli.command(name="build-logs")
@click.argument("key", required=True)
@click.option(
    "--from", "from_timestamp", help=f"The start time of the logs. {TIME_FORMAT_HELP}"
)
@click.option(
    "--to", "to_timestamp", help=f"The end time of the logs. {TIME_FORMAT_HELP}"
)
@click.option(
    "--limit",
    type=int,
    help=f"The number of logs to return. The acceptable range is {MIN_LOGS_LIMIT}-{MAX_LOGS_LIMIT}.",
)
@click.option(
    "--loglevel",
    type=click.Choice([level.value for level in constants.LogLevel]),
    default=constants.LogLevel.INFO.value,
    help="The log level to use.",
)
def get_deployment_build_logs(
    key: str,
    from_timestamp: str | None,
    to_timestamp: str | None,
    limit: int | None,
    loglevel: str,
):
    """Get the build logs for a deployment.

    Args:
        key: The name of the deployment.
        from_timestamp: The start time of the logs.
        to_timestamp: The end time of the logs.
        limit: The maximum number of logs to return.
        loglevel: The log level to use.

    """


@deployments_cli.command(name="regions")
@click.option(
    "--loglevel",
    type=click.Choice([level.value for level in constants.LogLevel]),
    default=constants.LogLevel.INFO.value,
    help="The log level to use.",
)
@click.option(
    "--json/--no-json",
    "-j",
    "as_json",
    is_flag=True,
    help="Whether to output the result in json format.",
)
def get_deployment_regions(loglevel: str, as_json: bool):
    """List all the regions of the hosting service.

    Args:
        loglevel: The log level to use.
        as_json: Whether to output the result in json format.

    """


@deployments_cli.command(name="share")
@click.option(
    "--url",
    help="The URL of the deployed app to share. If not provided, the latest deployment is shared.",
)
@click.option(
    "--loglevel",
    type=click.Choice([level.value for level in constants.LogLevel]),
    default=constants.LogLevel.INFO.value,
    help="The log level to use.",
)
def share_deployment(url: str | None, loglevel: str):
    """Share a deployment.

    Args:
        url: The URL of the deployed app to share.
        loglevel: The log level to use.

    """


def _patch_typer(click_instance: click.Command) -> typer.Typer:
    import functools

    import typer
    from typer.models import TyperInfo

    fake_typer_app = typer.Typer(add_completion=False)

    fake_typer_app.callback()(lambda: None)

    original_get_group_from_info = typer.main.get_group_from_info

    def get_group_from_info(group_info: TyperInfo, *args, **kwargs):
        if group_info.typer_instance is fake_typer_app:
            click_instance.name = group_info.name
            return click_instance
        return original_get_group_from_info(group_info, *args, **kwargs)

    functools.update_wrapper(
        get_group_from_info,
        original_get_group_from_info,
    )

    typer.main.get_group_from_info = get_group_from_info

    return fake_typer_app


if (
    find_spec("typer") is not None
    and find_spec("typer.core") is not None
    and find_spec("typer.models") is not None
):
    deployments_cli = _patch_typer(deployments_cli)  # pyright: ignore[reportAssignmentType]
