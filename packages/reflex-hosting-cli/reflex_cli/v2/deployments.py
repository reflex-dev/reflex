"""The Hosting CLI deployments sub-commands."""

from __future__ import annotations

import importlib.metadata
from importlib.util import find_spec
from typing import TYPE_CHECKING

import click
from packaging import version

from reflex_cli import constants
from reflex_cli.utils import console
from reflex_cli.v2.apps import apps_cli
from reflex_cli.v2.project import project_cli
from reflex_cli.v2.secrets import secrets_cli
from reflex_cli.v2.vmtypes_regions import vm_types_regions_cli

if TYPE_CHECKING:
    import typer


@click.group
@click.pass_context
def hosting_cli(ctx: click.Context) -> None:
    """The Hosting CLI.

    This CLI is used to manage the Reflex cloud hosting service.
    It provides commands for managing apps, projects, secrets, and VM types/regions.

    """
    if _reflex_version < constants.ReflexHostingCli.MINIMUM_REFLEX_VERSION:
        ctx.fail(
            f"Reflex version {_reflex_version} is not compatible with reflex-hosting-cli. "
            f"Please upgrade Reflex to at least version {constants.ReflexHostingCli.MINIMUM_REFLEX_VERSION}."
        )
    if _reflex_version < constants.ReflexHostingCli.RECOMMENDED_REFLEX_VERSION:
        console.warn(
            f"Support for Reflex version {_reflex_version} in reflex-hosting-cli is deprecated. "
            f"Please upgrade Reflex to at least version {constants.ReflexHostingCli.RECOMMENDED_REFLEX_VERSION}."
        )
    check_version()


_reflex_version = version.parse(importlib.metadata.version("reflex"))


hosting_cli.add_command(
    apps_cli,
    name="apps",
)
hosting_cli.add_command(
    project_cli,
    name="project",
)
hosting_cli.add_command(
    secrets_cli,
    name="secrets",
)
for name, command in vm_types_regions_cli.commands.items():
    # Add the command to the hosting CLI
    hosting_cli.add_command(command, name=name)


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
    hosting_cli = _patch_typer(hosting_cli)  # pyright: ignore[reportAssignmentType]

TIME_FORMAT_HELP = "Accepts ISO 8601 format, unix epoch or time relative to now. For time relative to now, use the format: <d><unit>. Valid units are d (day), h (hour), m (minute), s (second). For example, 1d for 1 day ago from now."
MIN_LOGS_LIMIT = 50
MAX_LOGS_LIMIT = 1000


def check_version():
    """Callback to be invoked for all hosting CLI commands.

    Checks if the installed version of the package is up-to-date with the latest version available on PyPI.
    If a newer version is available, it prints a warning message and exits.

    Raises:
        Exit: If a newer version is available, prompting the user to upgrade.

    """
    import httpx

    package_name = constants.ReflexHostingCli.MODULE_NAME
    try:
        installed_version = importlib.metadata.version(package_name)
        response = httpx.get(f"https://pypi.org/pypi/{package_name}/json")
        response.raise_for_status()
        latest_version = response.json()["info"]["version"]

        if version.parse(installed_version) < version.parse(latest_version):
            console.error(
                f"Warning: You are using {package_name} version {installed_version}. "
                f"A newer version {latest_version} is available. "
                f"Upgrade using: pip install --upgrade {package_name}"
            )
            raise click.exceptions.Exit(1)
    except (
        importlib.metadata.PackageNotFoundError,
        httpx.RequestError,
        httpx.HTTPStatusError,
    ):
        # Silently pass if we can't check the version
        pass
