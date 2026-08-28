"""CLI for the hosting service."""

from __future__ import annotations

import contextlib
import dataclasses
import json
import logging
import os
import re
import shutil
import tempfile
import uuid
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import click
from packaging import version

from reflex_cli import constants
from reflex_cli.utils import console, log
from reflex_cli.utils.dependency import extract_domain

logger = logging.getLogger(__name__)


def login(
    loglevel: constants.LogLevel = constants.LogLevel.INFO,
) -> dict[str, Any]:
    """Authenticate with Reflex hosting service.

    Args:
        loglevel: The log level to use.

    Returns:
        Information about the newly logged in user or empty dict if already
        logged in.

    Raises:
        SystemExit: If the command fails.

    """
    from reflex_cli.utils import hosting

    # Set the log level.
    console.set_log_level(loglevel)

    access_token, validated_info = hosting.authenticated_token()
    if access_token:
        console.print("You already logged in.")
        return {}

    # If not already logged in, open a browser window/tab to the login page.
    access_token, validated_info = hosting.authenticate_on_browser()

    if not access_token:
        logger.error("Unable to authenticate. Please try again or contact support.")
        raise SystemExit(1)

    console.print("Successfully logged in.")
    return validated_info


def logout(
    loglevel: constants.LogLevel = constants.LogLevel.INFO,
):
    """Log out of access to Reflex hosting service.

    Args:
        loglevel: The log level to use.

    """
    from reflex_cli.utils import hosting

    console.set_log_level(loglevel)

    logger.debug("Deleting access token from config locally")
    hosting.delete_token_from_config()
    logger.log(log.SUCCESS, "Successfully logged out.")


def _resolve_gcp_connection(
    gcp_connection: str | None, target: str | None, client: Any
) -> dict[str, Any] | None:
    """Resolve ``--gcp-connection`` against the org's named GCP connections.

    Args:
        gcp_connection: The connection name (or id) the user asked for.
        target: The provider this deploy is targeting.
        client: The authenticated client.

    Returns:
        The matching connection dict, or None when none was named.

    Raises:
        Exit: If the deploy is not targeting GCP, the connections cannot be
            read, or nothing matches the given name.

    """
    from reflex_cli.utils import hosting

    if not gcp_connection:
        return None
    if target != hosting.PROVIDER_GCP:
        logger.error(
            "--gcp-connection only applies to Google Cloud deploys. Pass "
            "--provider gcp to deploy through a connected GCP account."
        )
        raise click.exceptions.Exit(2)
    # Unlike the availability probe, a failure here aborts: the user named a
    # connection, and falling back to the org default would deploy into a
    # different GCP project than the one they asked for.
    try:
        connections = hosting.list_gcp_connections(client)
    except Exception as ex:
        logger.error(f"Unable to read this organization's GCP connections: {ex}")
        raise click.exceptions.Exit(1) from ex
    match = hosting.find_gcp_connection(connections, gcp_connection)
    if match is None:
        known = ", ".join(
            sorted(str(c.get("name")) for c in connections if c.get("name"))
        )
        connected = f" Connected: {known}." if known else ""
        logger.error(
            f"No GCP connection named {gcp_connection!r} in this organization."
            f"{connected} Run `reflex cloud providers connections` to list them."
        )
        raise click.exceptions.Exit(2)
    return match


# Cloud Run's service name grammar: lowercase, starts with a letter, ends
# alphanumeric, at most 49 characters. Mirrors the server's validation so a
# hostname that cannot be a service name is skipped here (the server mints one)
# instead of failing the deploy.
_GCP_SERVICE_NAME_RE = re.compile(r"^[a-z]([-a-z0-9]*[a-z0-9])?$")
_GCP_SERVICE_NAME_MAX_LENGTH = 49


def _gcp_service_name_from_hostname(hostname: str | None) -> str | None:
    """The --hostname value as a Cloud Run service name, if it can be one.

    On the first deploy to GCP the hostname doubles as the app's Cloud Run
    service name, so the service in the customer's console reads like the app's
    URL. A hostname the service-name grammar refuses (too long, leading digit,
    or the reserved ``app-<uuid>`` shape) is skipped with a note rather than
    failing the deploy — the server then mints a name from the app name.

    Args:
        hostname: The ``--hostname`` value, if the user passed one.

    Returns:
        The service name to request, or None to let the server choose.

    """
    if not hostname:
        return None
    name = hostname.strip().lower()
    reserved = False
    if name.startswith("app-"):
        try:
            uuid.UUID(name.removeprefix("app-"))
            reserved = True
        except ValueError:
            reserved = False
    if (
        not name
        or len(name) > _GCP_SERVICE_NAME_MAX_LENGTH
        or not _GCP_SERVICE_NAME_RE.match(name)
        or reserved
    ):
        logger.info(
            f"The hostname '{hostname}' cannot be used as the Cloud Run service "
            "name (lowercase letters, digits and hyphens, starting with a "
            f"letter, at most {_GCP_SERVICE_NAME_MAX_LENGTH} characters); one "
            "will be generated from the app name."
        )
        return None
    return name


def _pin_app_provider(
    app: dict[str, Any],
    target: str,
    connection: dict[str, Any] | None,
    client: Any,
    service_name: str | None = None,
) -> None:
    """Write the app's provider (and connection), aborting the deploy on refusal.

    Args:
        app: The resolved app dict (must contain "id").
        target: The backend provider value to pin.
        connection: The GCP connection to deploy through, if one was named.
        client: The authenticated client.
        service_name: The Cloud Run service name to request (GCP only); None
            keeps the app's current name or lets the server mint one.

    Raises:
        Exit: If the server refused the change.

    """
    from reflex_cli.utils import hosting

    result = hosting.set_app_provider(
        app["id"],
        target,
        client=client,
        provider_account_id=str(connection["id"]) if connection else None,
        service_name=service_name,
    )
    if isinstance(result, str) and result.startswith("set provider failed"):
        logger.error(result)
        raise click.exceptions.Exit(1)


def _resolve_deploy_provider(
    app: dict[str, Any],
    provider_arg: str | None,
    interactive: bool,
    app_was_created: bool,
    client: Any,
    gcp_connection: str | None = None,
    hostname: str | None = None,
) -> str | None:
    """Resolve and pin the hosting provider for this deploy.

    Decides whether the deploy targets Reflex Cloud or a connected GCP account,
    prompting interactively when GCP is available and no ``--provider`` was
    given, then pins the app to the chosen provider (switching, with a teardown
    warning, when it differs from the app's current provider).

    Args:
        app: The resolved app dict (must contain "id" and "name").
        provider_arg: The ``--provider`` value, if the user passed one.
        interactive: Whether to prompt.
        app_was_created: Whether the app was just created in this deploy (a
            switch then has nothing to tear down).
        client: The authenticated client.
        gcp_connection: The ``--gcp-connection`` value: which of the org's GCP
            connections to deploy through. Omitted leaves the app on the
            connection it already has, or the org's default the first time it
            targets GCP.
        hostname: The ``--hostname`` value. When this deploy is what first
            lands the app on GCP, it doubles as the requested Cloud Run service
            name; on later GCP deploys the name is already pinned to the live
            service, so it is not sent.

    Returns:
        The backend provider value in effect (Reflex Cloud's default or GCP), or
        None if left at the app's existing default.

    Raises:
        Exit: If ``--provider`` is invalid or a required switch fails.

    """
    from reflex_cli.utils import hosting

    current = app.get("provider")

    if provider_arg is not None:
        # Explicit --provider always wins; validated by the caller already.
        target = hosting.normalize_provider(provider_arg)
    else:
        gcp_status = hosting.gcp_deploy_available(client)
        if not gcp_status or not interactive:
            # No GCP connected, or non-interactive with no explicit choice: keep
            # whatever the app already targets.
            target = current
        else:
            region = gcp_status.get("region")
            console.print(
                "This organization has Google Cloud connected"
                + (f" (region {region})" if region else "")
                + "."
            )
            default_choice = (
                "gcp" if current == hosting.PROVIDER_GCP else "reflex-cloud"
            )
            choice = console.ask(
                "Where would you like to deploy?",
                choices=["reflex-cloud", "gcp"],
                default=default_choice,
            )
            target = hosting.normalize_provider(choice)

    connection = _resolve_gcp_connection(gcp_connection, target or current, client)

    if target is None or target == (current or hosting.PROVIDER_REFLEX_CLOUD):
        # The provider is unchanged. A named connection is still written: it
        # repoints the app at a different GCP project, which is a change even
        # when the provider it deploys to is not.
        if connection is not None:
            _pin_app_provider(app, hosting.PROVIDER_GCP, connection, client)
            project = (
                f" (project {connection['project_id']})"
                if connection.get("project_id")
                else ""
            )
            logger.info(
                f"Deploying through GCP connection '{connection.get('name')}'{project}."
            )
        return target or current

    if not app_was_created and current is not None:
        logger.warning(
            f"Switching '{app['name']}' from {hosting.provider_display_name(current)} "
            f"to {hosting.provider_display_name(target)} tears down its current "
            "deployment on the old provider; this deploy brings it back up on the "
            "new one."
        )
        if (
            interactive
            and console.ask("Continue?", choices=["y", "n"], default="n") != "y"
        ):
            logger.info("Deployment cancelled.")
            raise click.exceptions.Exit(0)

    # Only this pin — the one that first lands the app on GCP — carries a
    # service name. It is the moment the server would mint one, and the only
    # time a request cannot collide with a name already serving traffic.
    service_name = (
        _gcp_service_name_from_hostname(hostname)
        if target == hosting.PROVIDER_GCP
        else None
    )
    _pin_app_provider(app, target, connection, client, service_name=service_name)
    via = f" through connection '{connection.get('name')}'" if connection else ""
    logger.info(f"Deploying to {hosting.provider_display_name(target)}{via}.")
    if service_name:
        logger.info(f"Requested Cloud Run service name '{service_name}'.")
    return target


@contextlib.contextmanager
def _restore_provider_on_failure(
    app: dict[str, Any], switched_from: str | None, client: Any
) -> Iterator[None]:
    """Re-pin the previous provider if the deploy fails after a switch.

    Switching a deployed app to a new provider tears down its old resources up
    front, so a failure in a later step (hostname, export, deploy creation)
    would strand the app on the new provider. On failure, best-effort restore
    the previous provider so its last deployment stays a valid
    ``reflex cloud apps rollback`` target for recovery.

    Args:
        app: The resolved app dict (must contain "id" and "name").
        switched_from: The provider to restore to, or None if no destructive
            switch happened (nothing to undo).
        client: The authenticated client.

    Yields:
        None.

    """
    from reflex_cli.utils import hosting

    try:
        yield
    except BaseException:
        if switched_from is not None:
            label = hosting.provider_display_name(switched_from)
            restore = hosting.set_app_provider(app["id"], switched_from, client=client)
            if isinstance(restore, str) and restore.startswith("set provider failed"):
                logger.warning(
                    f"Deploy failed after switching '{app['name']}' provider, and "
                    f"restoring {label} also failed: {restore}. Check the app in "
                    "the Reflex Cloud dashboard."
                )
            else:
                logger.warning(
                    f"Deploy failed after switching provider; restored "
                    f"'{app['name']}' to {label}. Recover its previous deployment "
                    "with `reflex cloud apps rollback`."
                )
        raise


@contextlib.contextmanager
def _warn_if_bounds_outlive_deploy(app_name: str, applied: bool) -> Iterator[None]:
    """Report instance bounds that stuck when the deploy they were for failed.

    Bounds are app state, not deployment state: there is no deployment-scoped
    rollback to undo them, and the CLI has no way to read what they were before
    to restore them. So when the submit they were applied for does not produce a
    deployment -- rejected, raised, or interrupted -- say so, rather than let the
    app's next deployment pick them up unannounced.

    Args:
        app_name: The name of the app whose bounds were changed.
        applied: Whether bounds were actually applied; a no-op when False.

    Yields:
        None.

    """
    try:
        yield
    except BaseException:
        if applied:
            logger.warning(
                f"The new instance bounds were applied to '{app_name}' and will "
                "be used by its next deployment, even though this deploy failed."
            )
        raise


def _apply_full_deploy(
    app: dict[str, Any],
    full_deploy: bool | None,
    provider: str | None,
    client: Any,
) -> bool:
    """Set the app's hosting mode, before its hostname is reserved.

    In full-deploy mode the frontend is served from the provider's own
    container, on the same origin as the backend, so nothing is hosted on
    Reflex's CDN. The reserved hostname is what the frontend is compiled
    against, which is why the mode has to be written before it is reserved.

    Args:
        app: The resolved app dict (must contain "id" and "name").
        full_deploy: The requested mode; None leaves the app's mode alone.
        provider: The provider this deploy is targeting.
        client: The authenticated client.

    Returns:
        Whether a running app was stopped to apply the change.

    Raises:
        Exit: If full deploy was asked for on a provider that cannot serve it,
            or the server refused the change.

    """
    from reflex_cli.utils import hosting

    if full_deploy is None:
        return False
    if provider != hosting.PROVIDER_GCP:
        if full_deploy:
            logger.error(
                "--full-deploy serves the frontend from the provider's own "
                "container, which only the Google Cloud target supports. Pass "
                "--provider gcp, or drop --full-deploy."
            )
            raise click.exceptions.Exit(2)
        # Nothing to turn off: the mode is GCP-only and the provider write
        # clears it for an app leaving GCP, so this is a guaranteed no-op. Skip
        # the round trip rather than refuse it -- a config file carrying
        # `full_deploy: false` must not fail a Reflex Cloud deploy.
        return False

    try:
        result = hosting.set_app_full_deploy(app["id"], full_deploy, client=client)
    except BaseException:
        # A dropped connection says nothing about whether the server applied the
        # change, and applying it stops a running app, so hedge rather than
        # re-raise into a failure path that reports nothing about the app being
        # down. The warning context below is not entered on this path.
        logger.warning(
            f"Lost contact while changing the hosting mode of '{app['name']}'. "
            "The change stops a running app, and it may have been applied, so "
            "check the app in the Reflex Cloud dashboard before relying on it "
            "still being up."
        )
        raise
    if isinstance(result, str):
        logger.error(result)
        raise click.exceptions.Exit(1)

    stopped = bool(result.get("stopped"))
    if stopped and not result.get("stop_confirmed", True):
        logger.warning(
            f"'{app['name']}' was stopped to change its hosting mode, but the "
            "provider did not confirm the teardown. This deploy may be refused "
            "until that clears; check the app in the Reflex Cloud dashboard."
        )
    if result.get("full_deploy"):
        logger.info(
            "Full deploy: the frontend is served from the provider, on the same "
            "origin as the backend."
        )
    return stopped


@contextlib.contextmanager
def _warn_if_full_deploy_outlives_deploy(
    app_name: str, stopped: bool
) -> Iterator[None]:
    """Report an app left down by a hosting-mode flip whose deploy then failed.

    Flipping the mode stops a running app so the redeploy brings it back up in
    the new one. When that redeploy does not happen, the app stays down, and
    rollback is not a way back: the flip destroyed the images its previous
    deployments were built from, and those were built for the old mode anyway.

    Args:
        app_name: The name of the app whose mode was changed.
        stopped: Whether the flip actually stopped a running app; a no-op when
            False.

    Yields:
        None.

    """
    try:
        yield
    except BaseException:
        if stopped:
            logger.warning(
                f"'{app_name}' was stopped to change its hosting mode and this "
                "deploy did not bring it back up, so it stays down until one "
                "succeeds. Its earlier deployments are not rollback targets: "
                "they were built for the previous hosting mode."
            )
        raise


def deploy(
    export_fn: Callable[[str, str, str, bool, bool, bool, bool], None]
    | Callable[[str, str, str, bool, bool, bool], None],
    app_name: str | None = None,
    description: str | None = None,
    regions: list[str] | None = None,
    project: str | None = None,
    envs: list[str] | None = None,
    vmtype: str | None = None,
    hostname: str | None = None,
    interactive: bool = True,
    envfile: str | None = None,
    loglevel: constants.LogLevel = constants.LogLevel.INFO,
    token: str | None = None,
    config_path: str | None = None,
    env: str | None = None,
    project_name: str | None = None,
    app_id: str | None = None,
    provider: str | None = None,
    deployment_description: str | None = None,
    # Appended rather than grouped next to `vmtype` so existing positional
    # callers keep binding to the same parameters.
    min_instances: int | None = None,
    max_instances: int | None = None,
    gcp_connection: str | None = None,
    full_deploy: bool | None = None,
    strategy: str | None = None,
    **kwargs,
):
    """Deploy the app to the Reflex hosting service.

    Args:
        app_name: The name of the app.
        export_fn: The function from the Reflex main framework to export the app.
        description: The app's description.
        regions: The regions to deploy to.
        project: The project to deploy to.
        envs: The environment variables to set.
        vmtype: The VM type to allocate.
        hostname: The hostname to use for the frontend. On the deploy that
            first lands the app on GCP it also names the app's Cloud Run
            service, when the service-name grammar allows it.
        interactive: Whether to use interactive mode.
        envfile: The path to an env file to use. Will override any envs set manually.
        loglevel: The log level to use.
        token: The authentication token.
        config_path: The path to the config file.
        env: The environment to use for deployment.
        project_name: The name of the project.
        app_id: The ID of the app.
        provider: The hosting provider to deploy to ("reflex-cloud" or "gcp").
            When omitted and the org has GCP connected, the CLI prompts in
            interactive mode.
        deployment_description: An optional changelog note recorded on this
            deployment and shown in ``reflex cloud apps history``.
        min_instances: The minimum number of instances to keep running. Left at
            the app's current value when omitted.
        max_instances: The maximum number of instances to scale out to. Left at
            the app's current value when omitted.
        gcp_connection: Which of the org's GCP connections to deploy through,
            by name or id. Only valid when deploying to GCP; omitted leaves the
            app on the connection it already has, or the org's default the
            first time it targets GCP.
        full_deploy: Whether to serve the frontend from the provider's own
            container instead of Reflex's CDN (GCP only). None leaves the app's
            current hosting mode unchanged.
        strategy: The rollout strategy for this deployment ("immediate",
            "rolling", "bluegreen" or "canary").
        **kwargs: Additional keyword arguments.

    Raises:
        Exit: If the command fails.

    """
    import httpx

    from reflex_cli.utils import hosting

    authenticated_client = hosting.get_authenticated_client(
        token=token, interactive=interactive
    )

    # Set the log level.
    console.set_log_level(loglevel)
    project_id = project
    config = {}
    config_from_file = hosting.read_config(config_path, env=env)
    if config_from_file:
        config = dataclasses.asdict(config_from_file)

    packages = None
    include_db = False
    # If a config file is provided, use values from the file that are not provided as arguments.
    if config:
        if not regions:
            regions = config.get("regions", None)
        if not vmtype:
            vmtype = config.get("vmtype", None)
        if not hostname:
            hostname = config.get("hostname", None)
        if not envfile:
            envfile = config.get("envfile", None)
        if not project_id:
            project_id = config.get("project", None)
        if not project_name:
            project_name = config.get("projectname", None)
        if not provider:
            provider = config.get("provider", None)
        if not app_id:
            app_id = config.get("appid", None)
            if not isinstance(app_id, (str, type(None))):
                logger.error(
                    "app_id must be a string or None. Please check your config file."
                )
                raise SystemExit(1)
        if not packages:
            packages = config.get("packages", None)
        if not include_db:
            include_db = config.get("include_db", False)
        if not strategy:
            strategy = config.get("strategy", None)
        if not gcp_connection:
            gcp_connection = config.get("gcp_connection", None)
        if full_deploy is None:
            full_deploy = config.get("full_deploy", None)
        app_name = config.get("name", app_name)
        if not isinstance(app_name, (str, type(None))):
            logger.error(
                "app_name must be a string or None. Please check your config file."
            )
            raise SystemExit(1)
        if app_name == "default":
            # not sure if this is the best check?
            logger.error("Please set real config values in cloud.yml or pyproject.toml")
            raise SystemExit(1)
        if not description:
            description = config.get("description", None)

    project_id = hosting.normalize_project_id(project_id)

    if project_name and not project_id:
        result = hosting.search_project(
            project_name, client=authenticated_client, interactive=interactive
        )
        project_id = hosting.normalize_project_id(result.get("id")) if result else None

    selected_project_id = hosting.get_selected_project()

    validated_project: dict[str, Any] | None = None
    try:
        if not project_id:
            project_id = selected_project_id
        if project_id:
            validated_project = hosting.get_project(
                project_id, client=authenticated_client
            )
    except httpx.HTTPStatusError as ex:
        try:
            logger.error(ex.response.json().get("detail"))
        except json.JSONDecodeError:
            logger.error(ex.response.text)
        raise click.exceptions.Exit(1) from ex

    envs = envs or []

    # Validate --provider up front so an obvious typo fails before any work.
    if provider is not None and hosting.normalize_provider(provider) is None:
        logger.error(f"Unknown provider {provider!r}. Use 'reflex-cloud' or 'gcp'.")
        raise click.exceptions.Exit(2)

    if not app_name and not app_id:
        logger.error("Please provide a valid app name or ID for the deployed instance.")
        raise click.exceptions.Exit(1)

    # Tracks whether the app is created during this deploy: a provider switch on
    # a brand-new app has nothing to tear down, so we skip the switch warning.
    app_was_created = False
    try:
        if app_name and not app_id:
            search_project_id = project_id
            if interactive and not project:
                search_project_id = None

            app = hosting.search_app(
                app_name=app_name,
                project_id=search_project_id,
                client=authenticated_client,
                interactive=interactive,
            )
        else:
            app = hosting.get_app(app_id or "", client=authenticated_client)
            app_name = app.get("name")
    except click.exceptions.Exit:
        raise
    except Exception as ex:
        logger.error(f"Deployment failed: {ex}")
        raise click.exceptions.Exit(1) from ex

    if app and interactive and not project and not app_id:
        default_project_id = selected_project_id
        app_project_id = app.get("project_id")

        if app_project_id and (
            not default_project_id or app_project_id != default_project_id
        ):
            app_project_name = (app.get("project") or {}).get("name") or app_project_id
            if (
                console.ask(
                    f"Deploy to app '{app['name']}' in project '{app_project_name}'?",
                    choices=["y", "n"],
                    default="y",
                )
                != "y"
            ):
                logger.info("Deployment cancelled.")
                raise click.exceptions.Exit(0)

            project_id = app_project_id

    if not app and interactive:
        if (
            console.ask(
                f"No app with {app_name or app_id} found. Do you want to create a new app to deploy?",
                choices=["y", "n"],
                default="y",
            )
            == "y"
        ):
            if not project:
                needs_confirmation = not selected_project_id or (
                    project_id and project_id != selected_project_id
                )
                if needs_confirmation:
                    if project_id:
                        project_display_name = (
                            (
                                validated_project.get("name")
                                if validated_project
                                else None
                            )
                            or project_name
                            or project_id
                        )
                    else:
                        project_display_name = "your default project"
                        fallback_project_id = hosting.get_default_project(
                            authenticated_client
                        )
                        if fallback_project_id:
                            try:
                                fallback_project = hosting.get_project(
                                    fallback_project_id, client=authenticated_client
                                )
                                project_display_name = (
                                    fallback_project.get("name") or project_display_name
                                )
                            except Exception:
                                pass

                    if (
                        console.ask(
                            f"Create and deploy app '{app_name}' in project '{project_display_name}'?",
                            choices=["y", "n"],
                            default="y",
                        )
                        != "y"
                    ):
                        logger.info("Deployment cancelled.")
                        raise click.exceptions.Exit(0)

            if description is None:
                description = console.ask(
                    "App Description (Enter to skip)",
                )
            app = hosting.create_app(
                app_name=app_name or "",
                description=description,
                project_id=project_id,
                client=authenticated_client,
            )
            app_was_created = True
            logger.info(f"created app. \nName: {app['name']} \nId: {app['id']}")
        else:
            logger.error("Please create an app to deploy.")
            raise click.exceptions.Exit(1)
    elif not app:
        app = hosting.create_app(
            app_name=app_name or "",
            description=description or "",
            project_id=project_id,
            client=authenticated_client,
        )
        app_was_created = True
        logger.info(f"created app. \nName: {app['name']} \nId: {app['id']}")

    # Choose/confirm the hosting provider before reserving the hostname: the
    # reserved URL is baked into the exported frontend, and a GCP app resolves
    # to a *.run.app backend URL, so the provider must be pinned first.
    previous_provider = app.get("provider")
    effective_provider = _resolve_deploy_provider(
        app=app,
        provider_arg=provider,
        interactive=interactive,
        app_was_created=app_was_created,
        client=authenticated_client,
        gcp_connection=gcp_connection,
        hostname=hostname,
    )
    # A destructive provider switch on an already-deployed app tears its old
    # resources down; remember what to restore to if a later step fails.
    switched_from = (
        previous_provider
        if not app_was_created
        and previous_provider is not None
        and effective_provider != previous_provider
        else None
    )
    if effective_provider == hosting.PROVIDER_GCP:
        # GCP Cloud Run takes its region from the org's connected GCP account,
        # so a requested region is dropped. VM types are honored: the server
        # maps them onto Cloud Run CPU/memory limits.
        if regions:
            logger.info(
                "Ignoring --region for the Google Cloud target "
                "(the region comes from the connected GCP account)."
            )
        regions = None

    with contextlib.ExitStack() as failure_guards:
        failure_guards.enter_context(
            _restore_provider_on_failure(app, switched_from, authenticated_client)
        )
        if not app_name:
            logger.error("Please set an app name.")
            raise click.exceptions.Exit(1)

        # at this point, if project_id is None, the App should have the correct project_id and
        # we should use that going forward to pass validation checks.
        project_id = project_id or app.get("project_id")

        # Ahead of the hosting-mode change below, which stops a running app: a
        # deployment argument the server rejects would otherwise take the app
        # down for a deploy that never gets submitted. The provider switch above
        # is destructive too, but it has a restore; this does not.
        validation_message = hosting.validate_deployment_args(
            app_name=app_name,
            app_id=app.get("id"),
            project_id=project_id,
            regions=regions,
            vmtype=vmtype,
            hostname=hostname,
            client=authenticated_client,
        )

        if validation_message != "success":
            logger.error(validation_message)
            raise click.exceptions.Exit(1)

        # Inside the provider guard (a refused mode change must still restore the
        # provider it was asked for) and ahead of the reserve below, whose URL is
        # what the frontend is compiled against.
        failure_guards.enter_context(
            _warn_if_full_deploy_outlives_deploy(
                app["name"],
                _apply_full_deploy(
                    app, full_deploy, effective_provider, authenticated_client
                ),
            )
        )
        urls = hosting.get_hostname(
            app_id=app["id"],
            app_name=app["name"],
            hostname=hostname,
            client=authenticated_client,
        )
        if "error" in urls:
            logger.error(urls["error"])
            raise click.exceptions.Exit(1)
        server_url = (
            os.getenv("REFLEX_OVERRIDE_BACKEND_URL") or urls["server"]
        )  # backend
        host_url = (
            os.getenv("REFLEX_OVERRIDE_FRONTEND_URL") or urls["hostname"]
        )  # frontend
        processed_envs = hosting.process_envs(envs) if envs else None

        if envfile:
            try:
                from dotenv import (
                    dotenv_values,  # pyright: ignore[reportMissingImports]
                )

                processed_envs = dotenv_values(envfile)
            except ImportError:
                logger.error(
                    """The `python-dotenv` package is required to load environment variables from a file. Run `pip install "python-dotenv>=1.0.1"`."""
                )
                raise click.exceptions.Exit(1) from None

        # Compile the app in production mode: backend first then frontend.
        temporary_dir = tempfile.TemporaryDirectory()
        temporary_dir_path = Path(temporary_dir.name)

        import importlib.metadata

        rx_version = version.parse(importlib.metadata.version("reflex"))
        breaking_version = version.parse("0.7.6")
        # Try zipping backend first
        try:
            # Check if the reflex version is >= 0.7.6
            if rx_version <= breaking_version:
                export_fn(
                    str(temporary_dir_path),
                    server_url,
                    host_url,
                    False,
                    True,
                    True,
                )  # pyright: ignore[reportCallIssue]
            else:
                export_fn(
                    str(temporary_dir_path),
                    server_url,
                    host_url,
                    False,
                    True,
                    include_db,
                    True,  # pyright: ignore[reportCallIssue]
                )
        except Exception as ex:
            logger.error(f"Unable to export due to: {ex}")
            if temporary_dir_path.exists():
                shutil.rmtree(temporary_dir_path)
            raise click.exceptions.Exit(1) from ex

        # Zip frontend
        try:
            # Check if the reflex version is >= 0.7.6
            if rx_version <= breaking_version:
                export_fn(
                    str(temporary_dir_path), server_url, host_url, True, False, True
                )  # pyright: ignore[reportCallIssue]
            else:
                export_fn(
                    str(temporary_dir_path),
                    server_url,
                    host_url,
                    True,
                    False,
                    include_db,
                    True,  # pyright: ignore[reportCallIssue]
                )
        except ImportError as ie:
            logger.error(
                f"Encountered ImportError, did you install all the dependencies? {ie}"
            )
            if temporary_dir_path.exists():
                shutil.rmtree(temporary_dir_path)
            raise click.exceptions.Exit(1) from ie
        except Exception as ex:
            logger.error(f"Unable to export due to: {ex}")
            if temporary_dir_path.exists():
                shutil.rmtree(temporary_dir_path)
            raise click.exceptions.Exit(1) from ex

        # Instance bounds are app state that the deployment reads when it is
        # created, so they have to land before the submit below. Keep the two
        # calls adjacent: a bound applied earlier would outlive an export that
        # then fails, silently changing what the app's *next* deployment scales
        # to (and, for a non-zero minimum, what it costs to run).
        bounds_applied = min_instances is not None or max_instances is not None
        if bounds_applied:
            try:
                bounds_error = hosting.set_instance_bounds(
                    app_id=app["id"],
                    min_instances=min_instances,
                    max_instances=max_instances,
                    client=authenticated_client,
                )
            except BaseException:
                # A dropped connection says nothing about whether the server
                # applied the write, and the bounds are billable state, so hedge
                # rather than report either outcome as fact.
                logger.warning(
                    f"Lost contact while setting the instance bounds of "
                    f"'{app['name']}'; they may or may not have been applied. "
                    "Check the app in the Reflex Cloud dashboard before relying "
                    "on its scaling."
                )
                raise
            if bounds_error:
                logger.error(bounds_error)
                raise click.exceptions.Exit(1)

        with _warn_if_bounds_outlive_deploy(app["name"], bounds_applied):
            result = hosting.create_deployment(
                app_id=app.get("id"),
                app_name=app_name,
                project_id=project_id,
                regions=regions,
                zip_dir=Path(temporary_dir_path),
                hostname=extract_domain(host_url) if hostname else None,
                vmtype=vmtype,
                secrets=processed_envs,
                client=authenticated_client,
                packages=packages,
                strategy=strategy,
                description=deployment_description,
            )
            if "failed" in result:
                logger.error(result)
                raise click.exceptions.Exit(1)
    hosting_ui_url = f"{constants.Hosting.HOSTING_SERVICE_UI}/project/{app['project_id']}/app/{app['id']}/"
    console.print(
        f"deployment progress can now be viewed on the website: {hosting_ui_url}"
    )
    console.print(
        f"you are now safe to exit this command.\nfollow along with the deployment with the following command: \n  reflex cloud apps status {result} --watch"
    )
    status = hosting.watch_deployment_status(result, client=authenticated_client)
    if status is False:
        raise click.exceptions.Exit(1)
