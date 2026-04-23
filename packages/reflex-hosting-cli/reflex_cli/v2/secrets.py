"""Secrets commands for the Reflex Cloud CLI."""

from __future__ import annotations

import click

from reflex_cli import constants
from reflex_cli.utils import console
from reflex_cli.utils.exceptions import NotAuthenticatedError


@click.group()
def secrets_cli():
    """Commands for managing secrets."""
    pass


@secrets_cli.command(name="list")
@click.argument("app_id", required=False)
@click.option("--token", help="The authentication token.")
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
    help="Whether to output the result in JSON format.",
)
@click.option(
    "--interactive/--no-interactive",
    "-i",
    is_flag=True,
    default=True,
    help="Whether to use interactive mode.",
)
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

    try:
        authenticated_client = hosting.get_authenticated_client(
            token=token, interactive=interactive
        )

        if not app_id:
            config = hosting.read_config()
            if config:
                app_id = config.appid
                if not isinstance(app_id, (str, type(None))):
                    console.error(
                        "app_id must be a string or None. Please check your config file."
                    )
                    raise click.exceptions.Exit(1)

        if not app_id:
            console.error("No valid app_id provided.")
            raise click.exceptions.Exit(1)

        secrets = hosting.get_secrets(app_id=app_id, client=authenticated_client)
        if "failed" in secrets:
            console.error(secrets)
            raise click.exceptions.Exit(1)
        if as_json:
            console.print(secrets)
            return
        if secrets:
            headers = ["Keys"]
            table = [[key] for key in secrets]
            console.print_table(table, headers=headers)
        else:
            console.print(str(secrets))
    except NotAuthenticatedError as err:
        console.error("You are not authenticated. Run `reflex login` to authenticate.")
        raise click.exceptions.Exit(1) from err


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
@click.option(
    "--interactive/--no-interactive",
    "-i",
    is_flag=True,
    default=True,
    help="Whether to use interactive mode.",
)
def update_secrets(
    app_id: str | None,
    envfile: str | None,
    envs: tuple[str, ...],
    reboot: bool,
    token: str | None,
    loglevel: str,
    interactive: bool,
):
    """Update secrets for a given application."""
    from reflex_cli.utils import hosting

    console.set_log_level(loglevel)
    authenticated_client = hosting.get_authenticated_client(
        token=token, interactive=interactive
    )

    if not app_id:
        config = hosting.read_config()
        if config:
            app_id = config.appid
            if not isinstance(app_id, (str, type(None))):
                console.error(
                    "app_id must be a string or None. Please check your config file."
                )
                raise click.exceptions.Exit(1)

    if not app_id:
        console.error("No valid app_id provided.")
        raise click.exceptions.Exit(1)

    if envfile is None and not envs:
        console.error("--envfile or --env must be provided")
        raise click.exceptions.Exit(1)

    if envfile and envs:
        console.warn("--envfile is set; ignoring --env")

    secrets = {}

    if envfile:
        try:
            from dotenv import dotenv_values  # pyright: ignore[reportMissingImports]

            secrets = dotenv_values(envfile)
        except ImportError:
            console.error(
                """The `python-dotenv` package is required to load environment variables from a file. Run `pip install "python-dotenv>=1.0.1"`."""
            )

    else:
        secrets = hosting.process_envs(list(envs))
    hosting.update_secrets(
        app_id=app_id, secrets=secrets, reboot=reboot, client=authenticated_client
    )


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
@click.option(
    "--interactive/--no-interactive",
    "-i",
    is_flag=True,
    default=True,
    help="Whether to use interactive mode.",
)
def delete_secret(
    app_id: str | None,
    key: str,
    token: str | None,
    reboot: bool,
    loglevel: str,
    interactive: bool,
):
    """Delete a secret for a given application."""
    from reflex_cli.utils import hosting

    console.set_log_level(loglevel)
    try:
        authenticated_client = hosting.get_authenticated_client(
            token=token, interactive=interactive
        )

        if not app_id:
            config = hosting.read_config()
            if config:
                app_id = config.appid
                if not isinstance(app_id, (str, type(None))):
                    console.error(
                        "app_id must be a string or None. Please check your config file."
                    )
                    raise click.exceptions.Exit(1)

        if not app_id:
            console.error("No valid app_id provided.")
            raise click.exceptions.Exit(1)

        result = hosting.delete_secret(
            app_id=app_id, key=key, reboot=reboot, client=authenticated_client
        )
        if "failed" in result:
            console.error(result)
            raise click.exceptions.Exit(1)
        console.success("Successfully deleted secret.")
    except NotAuthenticatedError as err:
        console.error("You are not authenticated. Run `reflex login` to authenticate.")
        raise click.exceptions.Exit(1) from err
