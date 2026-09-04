"""The framework interface for the Reflex hosting CLI.

reflex-hosting-cli implements `reflex deploy` but does not depend on the
framework. Everything the deploy command needs from reflex goes through the
functions in this module, which the framework supports as a stable interface;
keep their signatures backward compatible.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

from reflex_base import constants
from reflex_base.config import get_config
from reflex_base.environment import environment

from reflex.utils import prerequisites
from reflex.utils.exec import arbitrate_ssr
from reflex.utils.export import export


@dataclasses.dataclass(frozen=True)
class DeployPrep:
    """What the hosting CLI needs from the framework to run a deploy."""

    app_name: str
    loglevel: constants.LogLevel
    ssr: bool


def prepare_deploy(*, ssr: bool = True) -> DeployPrep:
    """Prepare the current app directory for a deploy.

    Sets the DEPLOY compile context, reconciles the ssr flag with the
    REFLEX_SSR environment variable, ensures the cwd is an initialized reflex
    app, and warns when the hosting CLI package is outdated.

    Args:
        ssr: Whether the frontend should be exported with server side rendering.

    Returns:
        The app config values and effective SSR setting the deploy should use.
    """
    from reflex.reflex import _init

    config = get_config()

    environment.REFLEX_COMPILE_CONTEXT.set(constants.CompileContext.DEPLOY)
    ssr = arbitrate_ssr(ssr)

    prerequisites.assert_in_reflex_dir()
    if prerequisites.needs_reinit():
        _init(name=config.app_name)
    prerequisites.check_latest_package_version(constants.ReflexHostingCLI.MODULE_NAME)

    return DeployPrep(app_name=config.app_name, loglevel=config.loglevel, ssr=ssr)


def export_for_deploy(
    *,
    zip_dest_dir: str,
    api_url: str,
    deploy_url: str,
    frontend: bool,
    backend: bool,
    upload_db_file: bool,
    zipping: bool,
    backend_excluded_dirs: tuple[Path, ...] = (),
    prerender_routes: bool = True,
) -> None:
    """Export the app as deploy artifacts for the hosting service.

    Args:
        zip_dest_dir: The directory to export the zip files to.
        api_url: The API URL the deployed backend will be served from.
        deploy_url: The URL the deployed frontend will be served from.
        frontend: Whether to export the frontend.
        backend: Whether to export the backend.
        upload_db_file: Whether to include the sqlite db file in the backend zip.
        zipping: Whether to zip the exported app.
        backend_excluded_dirs: Files or directories to exclude from the backend zip.
        prerender_routes: Whether to prerender the routes.
    """
    export(
        zip_dest_dir=zip_dest_dir,
        api_url=api_url,
        deploy_url=deploy_url,
        frontend=frontend,
        backend=backend,
        zipping=zipping,
        loglevel=get_config().loglevel.subprocess_level(),
        upload_db_file=upload_db_file,
        backend_excluded_dirs=backend_excluded_dirs,
        prerender_routes=prerender_routes,
    )
