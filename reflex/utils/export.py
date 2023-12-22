"""Export utilities."""
import os
from pathlib import Path
from typing import Optional

from reflex import constants
from reflex.config import get_config
from reflex.utils import build, console, exec, prerequisites, telemetry

config = get_config()


def export(
    zipping: bool = True,
    frontend: bool = True,
    backend: bool = True,
    zip_dest_dir: str = os.getcwd(),
    upload_db_file: bool = False,
    api_url: Optional[str] = None,
    deploy_url: Optional[str] = None,
    loglevel: constants.LogLevel = console._LOG_LEVEL,
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
        loglevel: The log level to use. Defaults to console._LOG_LEVEL.
    """
    # Set the log level.
    console.set_log_level(loglevel)

    # Override the config url values if provided.
    if api_url is not None:
        config.api_url = str(api_url)
        console.debug(f"overriding API URL: {config.api_url}")
    if deploy_url is not None:
        config.deploy_url = str(deploy_url)
        console.debug(f"overriding deploy URL: {config.deploy_url}")

    # Show system info
    exec.output_system_info()

    # Check that the app is initialized.
    prerequisites.check_initialized(frontend=frontend)

    # Compile the app in production mode and export it.
    console.rule("[bold]Compiling production app and preparing for export.")

    if frontend:
        # Update some parameters for export
        prerequisites.update_next_config(export=True)
        # Ensure module can be imported and app.compile() is called.
        prerequisites.get_compiled_app()
        # Set up .web directory and install frontend dependencies.
        build.setup_frontend(Path.cwd())

    # Export the app.
    build.export(
        backend=backend,
        frontend=frontend,
        zip=zipping,
        zip_dest_dir=zip_dest_dir,
        deploy_url=config.deploy_url,
        upload_db_file=upload_db_file,
    )

    # Post a telemetry event.
    telemetry.send("export")
