"""Export utilities."""

import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from reflex_base import constants
from reflex_base.config import get_config
from reflex_base.environment import environment
from reflex_base.utils import console

from reflex.utils import build, exec, prerequisites, telemetry


def export(
    zipping: bool = True,
    frontend: bool = True,
    backend: bool = True,
    zip_dest_dir: str = str(Path.cwd()),
    upload_db_file: bool = False,
    api_url: str | None = None,
    deploy_url: str | None = None,
    env: constants.Env = constants.Env.PROD,
    loglevel: constants.LogLevel = console._LOG_LEVEL,
    backend_excluded_dirs: tuple[Path, ...] = (),
    prerender_routes: bool = True,
):
    """Export the app to a zip file.

    Args:
        zipping: Whether to zip the exported app. Defaults to True.
        frontend: Whether to export the frontend. Defaults to True.
        backend: Whether to export the backend. Defaults to True.
        zip_dest_dir: The directory to export the zip file to. Defaults to os.getcwd().
        upload_db_file: Whether to upload the database file. Defaults to False.
        api_url: The API URL to use. Defaults to None.
        deploy_url: The deploy URL to use. Defaults to None.
        env: The environment to use. Defaults to constants.Env.PROD.
        loglevel: The log level to use. Defaults to console._LOG_LEVEL.
        backend_excluded_dirs: A tuple of files or directories to exclude from the backend zip.  Defaults to ().
        prerender_routes: Whether to prerender the routes. Defaults to True.
    """
    config = get_config()

    # Set the log level.
    console.set_log_level(loglevel)

    # Set env mode in the environment
    environment.REFLEX_ENV_MODE.set(env)

    # Override the config url values if provided.
    if api_url is not None:
        config._set_persistent(api_url=str(api_url))
        console.debug(f"overriding API URL: {config.api_url}")
    if deploy_url is not None:
        config._set_persistent(deploy_url=str(deploy_url))
        console.debug(f"overriding deploy URL: {config.deploy_url}")

    # Show system info
    exec.output_system_info()

    # Compile the app in production mode and export it.
    console.rule("[bold]Compiling production app and preparing for export.")

    start = time.monotonic()
    phase_durations: dict[str, float] = {}
    status = "success"
    detail: str | None = None

    @contextmanager
    def _time_phase(name: str) -> Iterator[None]:
        t0 = time.monotonic()
        try:
            yield
        finally:
            phase_durations[name] = time.monotonic() - t0

    try:
        if frontend:
            with _time_phase("compile_duration"):
                prerequisites.get_compiled_app(prerender_routes=prerender_routes)
            with _time_phase("build_duration"):
                build.setup_frontend(Path.cwd())
                build.build()
        if zipping:
            with _time_phase("zip_duration"):
                build.zip_app(
                    frontend=frontend,
                    backend=backend,
                    zip_dest_dir=zip_dest_dir,
                    include_db_file=upload_db_file,
                    backend_excluded_dirs=backend_excluded_dirs,
                )
    except Exception as exc:
        status = "failure"
        detail = type(exc).__name__
        raise
    finally:
        telemetry.send(
            "export",
            status=status,
            detail=detail,
            duration=time.monotonic() - start,
            compile_duration=phase_durations.get("compile_duration"),
            build_duration=phase_durations.get("build_duration"),
            zip_duration=phase_durations.get("zip_duration"),
        )
