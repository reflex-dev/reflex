"""The `reflex deploy` command.

This module hosts the managed-platform deploy command. The `reflex` CLI imports
it and registers it as `reflex deploy`.

The command body needs the reflex framework to compile and export the app, but
`reflex` is deliberately not a dependency of reflex-hosting-cli. Those imports
therefore stay inside the command body, which only ever runs under the reflex
CLI. Nothing at module scope may import `reflex`, so that this package stays
importable on its own.
"""

from __future__ import annotations

from pathlib import Path

import click
from reflex_base import constants
from reflex_base.config import get_config
from reflex_base.environment import environment
from reflex_base.utils.cli_options import log_options


@click.command(name="deploy")
@log_options
@click.option(
    "--app-name",
    help="The name of the app to deploy.",
)
@click.option(
    "--app-id",
    help="The ID of the app to deploy.",
)
@click.option(
    "-r",
    "--region",
    multiple=True,
    help="The regions to deploy to. `reflex cloud regions` For multiple envs, repeat this option, e.g. --region sjc --region iad",
)
@click.option(
    "--env",
    multiple=True,
    help="The environment variables to set: <key>=<value>. For multiple envs, repeat this option, e.g. --env k1=v2 --env k2=v2.",
)
@click.option(
    "--vmtype",
    help="Vm type id. Run `reflex cloud vmtypes` to get options.",
)
@click.option(
    "--min-instances",
    type=int,
    help="The minimum number of instances to keep running. Left unchanged when "
    "omitted. Only supported on apps deployed to Google Cloud.",
)
@click.option(
    "--max-instances",
    type=int,
    help="The maximum number of instances to scale out to. Left unchanged when "
    "omitted. Only supported on apps deployed to Google Cloud.",
)
@click.option(
    "--hostname",
    help="The hostname of the frontend.",
)
@click.option(
    "--provider",
    help="The hosting provider to deploy to: 'reflex-cloud' (default) or 'gcp' "
    "(a GCP account connected to your org, Enterprise tier). When omitted and "
    "GCP is connected, you'll be prompted in interactive mode. Deploys through "
    "Reflex Cloud either way; for an unmanaged deploy run under your own "
    "gcloud credentials, see `reflex cloud gcp-standalone`.",
)
@click.option(
    "--gcp-connection",
    help="Which of your organization's GCP connections to deploy through, by "
    "name. Run `reflex cloud providers connections` to list them. Only valid "
    "with --provider gcp; omitted keeps the app on the connection it already "
    "has, or your organization's default the first time it deploys to GCP.",
)
@click.option(
    "--full-deploy/--no-full-deploy",
    "full_deploy",
    default=None,
    help="Serve the frontend from the provider's own container, on the same "
    "origin as the backend, instead of Reflex's CDN. GCP only, Enterprise "
    "tier. Omitted leaves the app's hosting mode unchanged; changing it stops "
    "a running app so this deploy brings it back up in the new mode.",
)
@click.option(
    "--strategy",
    type=click.Choice(["immediate", "rolling", "bluegreen", "canary"]),
    help="How the new version rolls out. Defaults to the app's last strategy, "
    "or 'immediate'.",
)
@click.option(
    "--description",
    help="An optional note recorded on this deployment and shown in "
    "`reflex cloud apps history`.",
)
@click.option(
    "--interactive/--no-interactive",
    is_flag=True,
    default=True,
    help="Whether to list configuration options and ask for confirmation.",
)
@click.option(
    "--envfile",
    help="The path to an env file to use. Will override any envs set manually.",
)
@click.option(
    "--project",
    help="project id to deploy to",
)
@click.option(
    "--project-name",
    help="The name of the project to deploy to.",
)
@click.option(
    "--token",
    help="token to use for auth",
)
@click.option(
    "--config-path",
    "--config",
    help="path to the config file",
)
@click.option(
    "--exclude-from-backend",
    "backend_excluded_dirs",
    multiple=True,
    type=click.Path(exists=True, path_type=Path, resolve_path=True),
    help="Files or directories to exclude from the backend zip. Can be used multiple times.",
)
@click.option(
    "--server-side-rendering/--no-server-side-rendering",
    "--ssr/--no-ssr",
    "ssr",
    default=True,
    is_flag=True,
    help="Whether to enable server side rendering for the frontend.",
)
def deploy(
    app_name: str | None,
    app_id: str | None,
    region: tuple[str, ...],
    env: tuple[str],
    vmtype: str | None,
    min_instances: int | None,
    max_instances: int | None,
    hostname: str | None,
    provider: str | None,
    gcp_connection: str | None,
    full_deploy: bool | None,
    strategy: str | None,
    description: str | None,
    interactive: bool,
    envfile: str | None,
    project: str | None,
    project_name: str | None,
    token: str | None,
    config_path: str | None,
    backend_excluded_dirs: tuple[Path, ...] = (),
    ssr: bool = True,
):
    """Deploy the app to the Reflex hosting service."""
    from reflex.reflex import _init
    from reflex.utils import export as export_utils
    from reflex.utils import prerequisites
    from reflex_cli.utils import dependency
    from reflex_cli.v2 import cli as hosting_cli
    from reflex_cli.v2.deployments import check_version

    config = get_config()

    app_name = app_name or config.app_name

    check_version()

    environment.REFLEX_COMPILE_CONTEXT.set(constants.CompileContext.DEPLOY)

    if not environment.REFLEX_SSR.is_set():
        environment.REFLEX_SSR.set(ssr)
    elif environment.REFLEX_SSR.get() != ssr:
        ssr = environment.REFLEX_SSR.get()

    # Only check requirements if interactive.
    # There is user interaction for requirements update.
    if interactive:
        dependency.check_requirements()

    prerequisites.assert_in_reflex_dir()

    # Check if we are set up.
    if prerequisites.needs_reinit():
        _init(name=config.app_name)
    prerequisites.check_latest_package_version(constants.ReflexHostingCLI.MODULE_NAME)

    hosting_cli.deploy(
        app_name=app_name,
        app_id=app_id,
        export_fn=(
            lambda zip_dest_dir, api_url, deploy_url, frontend, backend, upload_db, zipping: (
                export_utils.export(
                    zip_dest_dir=zip_dest_dir,
                    api_url=api_url,
                    deploy_url=deploy_url,
                    frontend=frontend,
                    backend=backend,
                    zipping=zipping,
                    loglevel=config.loglevel.subprocess_level(),
                    upload_db_file=upload_db,
                    backend_excluded_dirs=backend_excluded_dirs,
                    prerender_routes=ssr,
                )
            )
        ),
        regions=list(region),
        envs=list(env),
        vmtype=vmtype,
        min_instances=min_instances,
        max_instances=max_instances,
        envfile=envfile,
        hostname=hostname,
        interactive=interactive,
        loglevel=config.loglevel,
        token=token,
        project=project,
        project_name=project_name,
        provider=provider,
        gcp_connection=gcp_connection,
        full_deploy=full_deploy,
        strategy=strategy,
        deployment_description=description,
        **({"config_path": config_path} if config_path is not None else {}),
    )
