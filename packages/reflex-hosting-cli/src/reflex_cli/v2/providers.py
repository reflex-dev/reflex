"""Cloud provider commands for the Reflex Cloud CLI.

Read-only visibility into the cloud providers connected to your organization
(currently GCP for bring-your-own-cloud deploys), including the named
connections ``reflex deploy --gcp-connection`` selects between. Connecting or
removing a provider account uploads and validates a service-account key and is
done from the Reflex Cloud dashboard (Organization → Cloud Providers).
"""

from __future__ import annotations

import json
import logging
from typing import Any

import click

from reflex_cli import constants
from reflex_cli.utils import console, log
from reflex_cli.utils.exceptions import NotAuthenticatedError

logger = logging.getLogger(__name__)


@click.group()
def providers_cli():
    """Commands for inspecting connected cloud providers."""


def _resolve_org_id(org_id: str | None, client: Any) -> str:
    """Resolve the organization id from --org-id or the caller's token.

    Args:
        org_id: The explicit org id, if given.
        client: The authenticated client.

    Returns:
        The resolved organization id.

    Raises:
        Exit: If no org id can be resolved.

    """
    from reflex_cli.utils import hosting

    resolved = org_id or hosting.get_token_org_id(client)
    if not resolved:
        logger.error("Could not determine your organization. Pass --org-id explicitly.")
        raise click.exceptions.Exit(1)
    return resolved


_CONNECTION_HEADERS = ["Name", "Provider", "Project", "Region", "Runs as", "Default"]

# What a connection's Cloud Run services run as when it names no service
# account of its own, and the two different reasons the CLI may not know.
_RUNTIME_SA_PROJECT_DEFAULT = "(project default)"
_RUNTIME_SA_UNKNOWN = "(needs org admin)"
_RUNTIME_SA_UNAVAILABLE = "(unavailable)"


def _runtime_service_accounts_of(accounts: list[dict]) -> dict[str, str]:
    """Index the runtime service accounts carried by a provider account listing.

    Args:
        accounts: The rows returned by ``hosting.list_provider_accounts``.

    Returns:
        ``{connection id: runtime service account}``, holding only the
        connections that name one.

    """
    return {
        str(account["id"]): str(runtime_sa)
        for account in accounts
        if account.get("id")
        and (runtime_sa := (account.get("config") or {}).get("runtime_service_account"))
    }


def _runtime_service_accounts(
    org_id: str, client: Any
) -> tuple[dict[str, str] | None, str]:
    """Look up what each of an org's connections runs its services as.

    Best effort: only the provider account listing carries the runtime service
    account, and that listing is limited to org admins, while this detail is
    worth showing to anyone who can read a status. A status that answers
    "can this org deploy to GCP" is not failed over an enrichment it could not
    read -- but the two reasons it could not are kept apart, since "you are not
    an admin" is a standing fact and a 5xx is a broken minute.

    Args:
        org_id: The organization id to query.
        client: The authenticated client.

    Returns:
        ``({connection id: runtime service account}, label)`` where the map is
        None if the listing could not be read, and the label is what to render
        for a connection the map does not answer for.

    """
    import httpx

    from reflex_cli.utils import hosting

    try:
        accounts = hosting.list_provider_accounts(org_id, client=client)
    except httpx.HTTPStatusError as ex:
        if ex.response.status_code in (
            httpx.codes.UNAUTHORIZED,
            httpx.codes.FORBIDDEN,
        ):
            logger.debug(f"Not permitted to read provider account details: {ex}")
            return None, _RUNTIME_SA_UNKNOWN
        logger.warning(f"Could not read the runtime service accounts: {ex}")
        return None, _RUNTIME_SA_UNAVAILABLE
    except Exception as ex:
        logger.warning(f"Could not read the runtime service accounts: {ex}")
        return None, _RUNTIME_SA_UNAVAILABLE
    return _runtime_service_accounts_of(accounts), _RUNTIME_SA_UNKNOWN


def _as_account_row(connection: dict) -> dict:
    """Reshape a GCP-status connection to look like a provider account row.

    `providers list --json` has emitted account rows since v0.1.69, so the
    fallback is reshaped to match rather than the reverse: one schema out of the
    command, and the one already released. What only the account listing carries
    -- who connected it, when, and its runtime service account -- is absent,
    which is exactly what the fallback could not read.

    Args:
        connection: A connection as the org's GCP status reports it.

    Returns:
        The same connection in the provider account listing's shape.

    """
    return {
        "id": connection.get("id"),
        "provider": connection.get("provider") or "gcp",
        "name": connection.get("name"),
        "is_default": connection.get("is_default"),
        "config": {
            key: connection[key]
            for key in ("project_id", "region")
            if connection.get(key)
        },
    }


def _connection_row(
    connection: dict,
    runtime_service_accounts: dict[str, str] | None,
    unknown_label: str = _RUNTIME_SA_UNKNOWN,
) -> list[str]:
    """Render one connection as a row of ``_CONNECTION_HEADERS``.

    Takes both shapes a connection arrives in: the provider account listing
    nests its project and region under ``config``, the org's GCP status carries
    them flat.

    Args:
        connection: The connection to render.
        runtime_service_accounts: The runtime service accounts by connection
            id, or None when they could not be read.
        unknown_label: What to render when they could not be read, which says
            why -- a caller who may not read them is not a caller whose read
            failed.

    Returns:
        The row's cells, in header order.

    """
    config = connection.get("config") or {}
    if runtime_service_accounts is None:
        runs_as = unknown_label
    else:
        runs_as = (
            runtime_service_accounts.get(str(connection.get("id") or ""))
            or _RUNTIME_SA_PROJECT_DEFAULT
        )
    return [
        str(connection.get("name") or ""),
        str(connection.get("provider") or "gcp"),
        str(connection.get("project_id") or config.get("project_id") or ""),
        str(connection.get("region") or config.get("region") or ""),
        runs_as,
        "yes" if connection.get("is_default") else "",
    ]


@providers_cli.command(name="status")
@click.option("--org-id", help="The organization ID (defaults to your token's org).")
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
    help="Whether to output the result in json format.",
)
@click.option(
    "--interactive/--no-interactive",
    "-i",
    is_flag=True,
    default=True,
    help="Whether to use interactive mode.",
)
def providers_status(
    org_id: str | None,
    token: str | None,
    loglevel: str,
    as_json: bool,
    interactive: bool,
):
    """Show whether your organization can deploy to Google Cloud (GCP)."""
    import httpx

    from reflex_cli.utils import hosting

    console.set_log_level(loglevel)
    try:
        authenticated_client = hosting.get_authenticated_client(
            token=token, interactive=interactive
        )
        org_id = _resolve_org_id(org_id, authenticated_client)
        try:
            status = hosting.get_gcp_provider_status(
                org_id, client=authenticated_client
            )
        except httpx.HTTPStatusError as ex:
            try:
                detail = ex.response.json().get("detail")
            except (ValueError, AttributeError):
                detail = ex.response.text
            logger.error(f"Failed to fetch GCP status: {detail}")
            raise click.exceptions.Exit(1) from ex

        if as_json:
            console.print(json.dumps(status))
            return

        configured = status.get("configured")
        allowed = status.get("allowed")
        if configured and allowed:
            logger.log(log.SUCCESS, "Google Cloud is connected and ready for deploys.")
        elif configured and not allowed:
            logger.warning(
                "Google Cloud is connected, but your plan does not allow GCP "
                "deploys. GCP deploys require the Enterprise tier."
            )
        elif not configured and allowed:
            logger.warning(
                "Google Cloud is not connected yet. Connect it from the Reflex "
                "Cloud dashboard: Organization -> Cloud Providers."
            )
        else:
            logger.warning(
                "Google Cloud is not connected, and GCP deploys require the "
                "Enterprise tier. Contact sales@reflex.dev to upgrade."
            )
        if status.get("project_id"):
            console.print(f"  Project: {status['project_id']}")
        if status.get("region"):
            console.print(f"  Region:  {status['region']}")

        connections = [
            connection
            for connection in (status.get("connections") or [])
            if isinstance(connection, dict)
        ]
        if connections:
            runtime_service_accounts, unknown_label = _runtime_service_accounts(
                org_id, authenticated_client
            )
            console.print(
                "\nConnections (pass one to `reflex deploy --gcp-connection`):"
            )
            console.print_table(
                [
                    _connection_row(connection, runtime_service_accounts, unknown_label)
                    for connection in connections
                ],
                headers=_CONNECTION_HEADERS,
                overflow="fold",
            )
    except NotAuthenticatedError as err:
        logger.error("You are not authenticated. Run `reflex login` to authenticate.")
        raise click.exceptions.Exit(1) from err


@providers_cli.command(name="list")
@click.option("--org-id", help="The organization ID (defaults to your token's org).")
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
    help="Whether to output the result in json format.",
)
@click.option(
    "--interactive/--no-interactive",
    "-i",
    is_flag=True,
    default=True,
    help="Whether to use interactive mode.",
)
def providers_list(
    org_id: str | None,
    token: str | None,
    loglevel: str,
    as_json: bool,
    interactive: bool,
):
    """List your organization's cloud provider connections.

    Each row is one connection: a customer cloud account apps can be deployed
    into. Pass a connection's name to `reflex deploy --gcp-connection` to
    deploy an app through it instead of the default one.
    """
    import httpx

    from reflex_cli.utils import hosting

    console.set_log_level(loglevel)
    try:
        authenticated_client = hosting.get_authenticated_client(
            token=token, interactive=interactive
        )
        org_id = _resolve_org_id(org_id, authenticated_client)
        runtime_service_accounts: dict[str, str] | None
        try:
            connections = hosting.list_provider_accounts(
                org_id, client=authenticated_client
            )
            runtime_service_accounts = _runtime_service_accounts_of(connections)
        except httpx.HTTPStatusError as ex:
            try:
                detail = ex.response.json().get("detail")
            except (ValueError, AttributeError):
                detail = ex.response.text
            if ex.response.status_code not in (
                httpx.codes.UNAUTHORIZED,
                httpx.codes.FORBIDDEN,
            ):
                logger.error(f"Failed to list provider accounts: {detail}")
                raise click.exceptions.Exit(1) from ex
            # The stored provider accounts are org-admin only, but anyone who
            # can deploy needs the connection names --gcp-connection selects
            # between, so fall back to the GCP status every member can read.
            logger.debug(f"Falling back to the GCP status listing: {detail}")
            try:
                connections = [
                    _as_account_row(connection)
                    for connection in hosting.list_gcp_connections(
                        authenticated_client, org_id=org_id
                    )
                ]
            except Exception as fallback_ex:
                logger.error(
                    f"Failed to list provider accounts: {detail}. Reading this "
                    f"organization's GCP status instead also failed: "
                    f"{fallback_ex}"
                )
                raise click.exceptions.Exit(1) from fallback_ex
            runtime_service_accounts = None

        if as_json:
            console.print(json.dumps(connections))
            return
        if not connections:
            console.print(
                "No cloud providers connected. Connect one from the Reflex Cloud "
                "dashboard: Organization -> Cloud Providers."
            )
            return
        console.print_table(
            [
                _connection_row(connection, runtime_service_accounts)
                for connection in connections
            ],
            headers=_CONNECTION_HEADERS,
            # A service account email is the point of the column and is too
            # long for it: wrap the cell rather than cut the value short.
            overflow="fold",
        )
    except NotAuthenticatedError as err:
        logger.error("You are not authenticated. Run `reflex login` to authenticate.")
        raise click.exceptions.Exit(1) from err


# The same listing under the name the deploy flag points at: --gcp-connection
# selects a connection, so `providers connections` is what a user reaches for.
# An alias rather than a second command -- two listings of one route would be
# two places for its columns to drift.
providers_cli.add_command(providers_list, name="connections")
