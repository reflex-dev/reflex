"""Cloud provider commands for the Reflex Cloud CLI.

Read-only visibility into the cloud providers connected to your organization
(currently GCP for bring-your-own-cloud deploys). Connecting or removing a
provider account uploads and validates a service-account key and is done from
the Reflex Cloud dashboard (Organization → Cloud Providers).
"""

from __future__ import annotations

import json
from typing import Any

import click

from reflex_cli import constants
from reflex_cli.utils import console
from reflex_cli.utils.exceptions import NotAuthenticatedError


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
        console.error(
            "Could not determine your organization. Pass --org-id explicitly."
        )
        raise click.exceptions.Exit(1)
    return resolved


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
            console.error(f"Failed to fetch GCP status: {detail}")
            raise click.exceptions.Exit(1) from ex

        if as_json:
            console.print(json.dumps(status))
            return

        configured = status.get("configured")
        allowed = status.get("allowed")
        if configured and allowed:
            console.success("Google Cloud is connected and ready for deploys.")
        elif configured and not allowed:
            console.warn(
                "Google Cloud is connected, but your plan does not allow GCP "
                "deploys. GCP deploys require the Enterprise tier."
            )
        elif not configured and allowed:
            console.warn(
                "Google Cloud is not connected yet. Connect it from the Reflex "
                "Cloud dashboard: Organization -> Cloud Providers."
            )
        else:
            console.warn(
                "Google Cloud is not connected, and GCP deploys require the "
                "Enterprise tier. Contact sales@reflex.dev to upgrade."
            )
        if status.get("project_id"):
            console.print(f"  Project: {status['project_id']}")
        if status.get("region"):
            console.print(f"  Region:  {status['region']}")
    except NotAuthenticatedError as err:
        console.error("You are not authenticated. Run `reflex login` to authenticate.")
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
    """List the cloud provider accounts connected to your organization."""
    import httpx

    from reflex_cli.utils import hosting

    console.set_log_level(loglevel)
    try:
        authenticated_client = hosting.get_authenticated_client(
            token=token, interactive=interactive
        )
        org_id = _resolve_org_id(org_id, authenticated_client)
        try:
            accounts = hosting.list_provider_accounts(
                org_id, client=authenticated_client
            )
        except httpx.HTTPStatusError as ex:
            try:
                detail = ex.response.json().get("detail")
            except (ValueError, AttributeError):
                detail = ex.response.text
            console.error(f"Failed to list provider accounts: {detail}")
            raise click.exceptions.Exit(1) from ex

        if as_json:
            console.print(json.dumps(accounts))
            return
        if not accounts:
            console.print(
                "No cloud providers connected. Connect one from the Reflex Cloud "
                "dashboard: Organization -> Cloud Providers."
            )
            return
        headers = ["Provider", "Project", "Region", "Connected"]
        rows = [
            [
                account.get("provider", ""),
                (account.get("config") or {}).get("project_id", ""),
                (account.get("config") or {}).get("region", ""),
                account.get("created_at", ""),
            ]
            for account in accounts
        ]
        console.print_table(rows, headers=headers)
    except NotAuthenticatedError as err:
        console.error("You are not authenticated. Run `reflex login` to authenticate.")
        raise click.exceptions.Exit(1) from err
