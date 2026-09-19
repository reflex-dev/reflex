"""Secrets commands for the Reflex Cloud CLI."""

from __future__ import annotations

import logging

import click

from reflex_cli import constants
from reflex_cli.utils import console, log
from reflex_cli.utils.output import interactive_option, json_option, print_json

logger = logging.getLogger(__name__)


@click.group()
def secrets_cli():
    """Commands for managing secrets."""


@secrets_cli.command(name="list")
@click.argument("app_id", required=False)
@click.option("--token", help="The authentication token.")
@click.option(
    "--loglevel",
    type=click.Choice([level.value for level in constants.LogLevel]),
    default=constants.LogLevel.INFO.value,
    help="The log level to use.",
)
@json_option
@interactive_option
def get_secrets(
    app_id: str | None,
    token: str | None,
    loglevel: str,
    as_json: bool,
    interactive: bool,
):
    """Retrieve secrets for a given application."""
    from reflex_cli.utils import hosting

    console.set_log_level(loglevel)

    with hosting.reporting_api_errors():
        authenticated_client = hosting.get_authenticated_client(
            token=token, interactive=interactive
        )

        if not app_id:
            config = hosting.read_config()
            if config:
                app_id = config.appid
                if not isinstance(app_id, (str, type(None))):
                    logger.error(
                        "app_id must be a string or None. Please check your config file."
                    )
                    raise click.exceptions.Exit(1)

        if not app_id:
            logger.error("No valid app_id provided.")
            raise click.exceptions.Exit(1)

        secrets = authenticated_client.api.apps.secrets.list(app_id)
        if as_json:
            print_json(secrets)
            return
        if secrets:
            console.print_table([[key] for key in secrets], headers=["Keys"])
        else:
            console.print(str(secrets))


@secrets_cli.command(name="update")
@click.argument("app_id", required=False)
@click.option(
    "--envfile",
    help="The path to an env file to use. Will override any envs set manually.",
)
@click.option(
    "--env",
    "envs",
    multiple=True,
    help="The environment variables to set: <key>=<value>. Required if envfile is not specified. For multiple envs, repeat this option, e.g. --env k1=v2 --env k2=v2.",
)
@click.option(
    "--reboot/--no-reboot",
    is_flag=True,
    help="Automatically reboot your site with the new secrets",
)
@click.option("--token", help="The authentication token.")
@click.option(
    "--loglevel",
    type=click.Choice([level.value for level in constants.LogLevel]),
    default=constants.LogLevel.INFO.value,
    help="The log level to use.",
)
@json_option
@interactive_option
def update_secrets(
    app_id: str | None,
    envfile: str | None,
    envs: tuple[str, ...],
    reboot: bool,
    token: str | None,
    loglevel: str,
    as_json: bool,
    interactive: bool,
):
    """Update secrets for a given application."""
    from reflex_cli.utils import hosting

    console.set_log_level(loglevel)
    with hosting.reporting_api_errors():
        authenticated_client = hosting.get_authenticated_client(
            token=token, interactive=interactive
        )

        if not app_id:
            config = hosting.read_config()
            if config:
                app_id = config.appid
                if not isinstance(app_id, (str, type(None))):
                    logger.error(
                        "app_id must be a string or None. Please check your config file."
                    )
                    raise click.exceptions.Exit(1)

        if not app_id:
            logger.error("No valid app_id provided.")
            raise click.exceptions.Exit(1)

        if envfile is None and not envs:
            logger.error("--envfile or --env must be provided")
            raise click.exceptions.Exit(1)

        if envfile and envs:
            logger.warning("--envfile is set; ignoring --env")

        if envfile:
            try:
                from dotenv import (  # pyright: ignore[reportMissingImports]
                    dotenv_values,
                )
            except ImportError:
                logger.error(
                    """The `python-dotenv` package is required to load environment variables from a file. Run `pip install "python-dotenv>=1.0.1"`."""
                )
                raise click.exceptions.Exit(1) from None
            # A bare `KEY` line with no `=` parses to None, which names no
            # value to set; only assignments become secrets.
            secrets = {
                name: value
                for name, value in dotenv_values(envfile).items()
                if value is not None
            }
        else:
            secrets = hosting.process_envs(list(envs))
        authenticated_client.api.apps.secrets.set(app_id, secrets, reboot=reboot)
        if as_json:
            # Names only: a value the caller just sent back to them is a secret
            # written into a log or a transcript.
            print_json({
                "app_id": app_id,
                "updated": sorted(secrets),
                "rebooted": reboot,
            })


@secrets_cli.command(name="delete")
@click.argument("app_id", required=False)
@click.argument("key", required=True)
@click.option("--token", help="The authentication token.")
@click.option(
    "--reboot/--no-reboot",
    is_flag=True,
    help="Automatically reboot your site with the new secrets",
)
@click.option(
    "--loglevel",
    type=click.Choice([level.value for level in constants.LogLevel]),
    default=constants.LogLevel.INFO.value,
    help="The log level to use.",
)
@json_option
@interactive_option
def delete_secret(
    app_id: str | None,
    key: str,
    token: str | None,
    reboot: bool,
    loglevel: str,
    as_json: bool,
    interactive: bool,
):
    """Delete a secret for a given application."""
    from reflex_cli.utils import hosting

    console.set_log_level(loglevel)
    with hosting.reporting_api_errors():
        authenticated_client = hosting.get_authenticated_client(
            token=token, interactive=interactive
        )

        if not app_id:
            config = hosting.read_config()
            if config:
                app_id = config.appid
                if not isinstance(app_id, (str, type(None))):
                    logger.error(
                        "app_id must be a string or None. Please check your config file."
                    )
                    raise click.exceptions.Exit(1)

        if not app_id:
            logger.error("No valid app_id provided.")
            raise click.exceptions.Exit(1)

        authenticated_client.api.apps.secrets.delete(app_id, key, reboot=reboot)
        if as_json:
            print_json({
                "app_id": app_id,
                "key": key,
                "deleted": True,
                "rebooted": reboot,
            })
            return
        logger.log(log.SUCCESS, "Successfully deleted secret.")
