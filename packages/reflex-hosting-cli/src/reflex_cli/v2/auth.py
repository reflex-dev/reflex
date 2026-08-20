"""Authentication inspection commands for the Reflex Cloud CLI."""

from __future__ import annotations

import hashlib
import json
import logging
import os

import click
from reflex_base.utils import log

from reflex_cli import constants
from reflex_cli.utils import console
from reflex_cli.utils.exceptions import TokenValidationError

logger = logging.getLogger(__name__)

# Identity fields copied from the control plane response, in display order.
_IDENTITY_FIELDS = ("email", "user_id", "org_id", "tier", "is_service_account")


def token_fingerprint(token: str) -> str:
    """Derive a non-reversible identifier for an access token.

    The same token always produces the same fingerprint, so two machines can be
    compared without revealing the token itself.

    Args:
        token: The access token to fingerprint.

    Returns:
        A short sha256-derived fingerprint, or an empty string if there is no token.

    """
    if not token:
        return ""
    return f"sha256:{hashlib.sha256(token.encode()).hexdigest()[:16]}"


_loglevel_option = click.option(
    "--loglevel",
    type=click.Choice([level.value for level in constants.LogLevel]),
    default=constants.LogLevel.INFO.value,
    help="The log level to use.",
)


@click.command()
@click.option("--token", help="The authentication token.")
@_loglevel_option
@click.option(
    "--json/--no-json",
    "-j",
    "as_json",
    is_flag=True,
    help="Whether to output the result in json format.",
)
def whoami_command(token: str | None, loglevel: str, as_json: bool):
    """Show which account the Reflex Cloud CLI is authenticating as.

    Reports the identity the control plane resolves the access token to, along
    with where that token was loaded from. Never starts a browser login and
    never prints the token itself.
    """
    from reflex_cli.utils import hosting

    console.set_log_level(loglevel)

    if token:
        access_token, source = token, hosting.TokenSource.OPTION
    else:
        access_token, source = hosting.get_existing_access_token_with_source()

    if not access_token:
        logger.error("Not logged in. Run `reflex login` to authenticate.")
        raise click.exceptions.Exit(1)

    try:
        validated_info = hosting.validate_token(access_token)
    except TokenValidationError as err:
        logger.error(
            f"The access token from the {source.value} was rejected: {err} "
            f"(auth request id: {err.request_id})"
        )
        raise click.exceptions.Exit(1) from err

    identity = {
        field: validated_info[field]
        for field in _IDENTITY_FIELDS
        if field in validated_info
    }
    identity["token_source"] = source.value
    identity["token_fingerprint"] = token_fingerprint(access_token)

    if as_json:
        console.print(json.dumps(identity))
        return

    console.print_table(
        [[field, str(value)] for field, value in identity.items()],
        headers=["field", "value"],
    )


@click.command()
@click.option(
    "--print",
    "print_token",
    is_flag=True,
    help="Print the stored access token to stdout.",
)
@click.option(
    "--set",
    "set_token",
    metavar="TOKEN",
    help="Validate TOKEN and store it as the access token.",
)
@click.option("--clear", is_flag=True, help="Remove the stored access token.")
@_loglevel_option
def token_command(print_token: bool, set_token: str | None, clear: bool, loglevel: str):
    """Inspect or replace the stored Reflex Cloud access token.

    Exactly one of --print, --set or --clear must be given. --print writes the
    raw token to stdout so it can be captured, e.g.
    `export REFLEX_ACCESS_TOKEN=$(reflex cloud token --print)`; stdout carries
    the token or nothing at all, so use `reflex cloud whoami` to inspect where
    the token came from.
    """
    from reflex_cli.utils import hosting

    console.set_log_level(loglevel)

    requested = [
        name
        for name, chosen in (
            ("--print", print_token),
            ("--set", set_token),
            ("--clear", clear),
        )
        if chosen
    ]
    if len(requested) != 1:
        raise click.UsageError(
            f"Specify exactly one of --print, --set or --clear (got {', '.join(requested) or 'none'})."
        )

    if print_token:
        # The shared console writes everything below ERROR to stdout, which
        # would land inside `$(reflex cloud token --print)` alongside the
        # token. Errors still go to stderr, so stdout stays exact either way.
        console.set_log_level(constants.LogLevel.ERROR)
        access_token, _ = hosting.get_existing_access_token_with_source()
        if not access_token:
            logger.error("No access token stored. Run `reflex login` to authenticate.")
            raise click.exceptions.Exit(1)
        # Bypass the console so the token is never wrapped or styled.
        click.echo(access_token)
        return

    if set_token:
        try:
            validated_info = hosting.validate_token(set_token)
        except TokenValidationError as err:
            logger.error(
                f"Token rejected, nothing was saved: {err} "
                f"(auth request id: {err.request_id})"
            )
            raise click.exceptions.Exit(1) from err

        hosting.save_token_to_config(set_token)
        stored, stored_source = hosting.get_existing_access_token_with_source()
        if stored != set_token or stored_source is not hosting.TokenSource.CONFIG:
            logger.error(
                f"Unable to persist the token to {constants.Hosting.HOSTING_JSON}."
            )
            raise click.exceptions.Exit(1)

        owner = validated_info.get("email") or validated_info.get("user_id")
        logger.log(
            log.SUCCESS,
            f"Saved the access token for {owner} ({token_fingerprint(set_token)}).",
        )
        return

    hosting.delete_token_from_config()
    # delete_token_from_config swallows filesystem errors, so confirm the
    # token is really gone rather than reporting an unverified success.
    _, stored_source = hosting.get_existing_access_token_with_source()
    if stored_source is hosting.TokenSource.CONFIG:
        logger.error(
            f"Unable to remove the access token from {constants.Hosting.HOSTING_JSON}."
        )
        raise click.exceptions.Exit(1)

    logger.log(log.SUCCESS, "Cleared the stored access token.")
    if os.environ.get("REFLEX_ACCESS_TOKEN"):
        logger.info(
            "REFLEX_ACCESS_TOKEN is still set; the CLI will authenticate with it."
        )
