"""Building the app and initializing all prerequisites."""

from __future__ import annotations

import json
import os
import random
import subprocess
from pathlib import Path
from typing import Optional, Union

from rich.progress import MofNCompleteColumn, Progress, TimeElapsedColumn

from reflex import constants
from reflex.config import get_config
from reflex.utils import console, path_ops, prerequisites
from reflex.utils.processes import new_process


def update_json_file(file_path: str, update_dict: dict[str, Union[int, str]]):
    """Update the contents of a json file.

    Args:
        file_path: the path to the JSON file.
        update_dict: object to update json.
    """
    fp = Path(file_path)
    # create file if it doesn't exist
    fp.touch(exist_ok=True)
    # create an empty json object if file is empty
    fp.write_text("{}") if fp.stat().st_size == 0 else None

    with open(fp) as f:  # type: ignore
        json_object: dict = json.load(f)
        json_object.update(update_dict)
    with open(fp, "w") as f:
        json.dump(json_object, f, ensure_ascii=False)


def set_reflex_project_hash():
    """Write the hash of the Reflex project to a REFLEX_JSON."""
    update_json_file(constants.REFLEX_JSON, {"project_hash": random.getrandbits(128)})


def set_environment_variables():
    """Write the upload url to a REFLEX_JSON."""
    update_json_file(
        constants.ENV_JSON,
        {
            "uploadUrl": constants.Endpoint.UPLOAD.get_url(),
            "eventUrl": constants.Endpoint.EVENT.get_url(),
            "pingUrl": constants.Endpoint.PING.get_url(),
        },
    )


def set_os_env(**kwargs):
    """Set os environment variables.

    Args:
        kwargs: env key word args.
    """
    for key, value in kwargs.items():
        if not value:
            continue
        os.environ[key.upper()] = value


def generate_sitemap_config(deploy_url: str):
    """Generate the sitemap config file.

    Args:
        deploy_url: The URL of the deployed app.
    """
    # Import here to avoid circular imports.
    from reflex.compiler import templates

    config = json.dumps(
        {
            "siteUrl": deploy_url,
            "generateRobotsTxt": True,
        }
    )

    with open(constants.SITEMAP_CONFIG_FILE, "w") as f:
        f.write(templates.SITEMAP_CONFIG(config=config))


def export_app(
    backend: bool = True,
    frontend: bool = True,
    zip: bool = False,
    deploy_url: Optional[str] = None,
    loglevel: constants.LogLevel = constants.LogLevel.ERROR,
):
    """Zip up the app for deployment.

    Args:
        backend: Whether to zip up the backend app.
        frontend: Whether to zip up the frontend app.
        zip: Whether to zip the app.
        deploy_url: The URL of the deployed app.
        loglevel: The log level to use.
    """
    # Remove the static folder.
    path_ops.rm(constants.WEB_STATIC_DIR)

    # Generate the sitemap file.
    command = "export"
    if deploy_url is not None:
        generate_sitemap_config(deploy_url)
        command = "export-sitemap"

    # Create a progress object
    progress = Progress(
        *Progress.get_default_columns()[:-1],
        MofNCompleteColumn(),
        TimeElapsedColumn(),
    )

    checkpoints = [
        "Linting and checking ",
        "Compiled successfully",
        "Route (pages)",
        "Collecting page data",
        "automatically rendered as static HTML",
        'Copying "static build" directory',
        'Copying "public" directory',
        "Finalizing page optimization",
        "Export successful",
    ]

    # Add a single task to the progress object
    task = progress.add_task("Creating Production Build: ", total=len(checkpoints))

    # Start the subprocess with the progress bar.
    try:
        with progress, new_process(
            [prerequisites.get_package_manager(), "run", command],
            cwd=constants.WEB_DIR,
        ) as export_process:
            assert export_process.stdout is not None, "No stdout for export process."
            for line in export_process.stdout:
                if loglevel == constants.LogLevel.DEBUG:
                    print(line, end="")

                # Check for special strings and update the progress bar.
                for special_string in checkpoints:
                    if special_string in line:
                        if special_string == "Export successful":
                            progress.update(task, completed=len(checkpoints))
                            break  # Exit the loop if the completion message is found
                        else:
                            progress.update(task, advance=1)
                            break

    except Exception as e:
        console.print(f"[red]Export process errored: {e}")
        console.print(
            "[red]Run in with [bold]--loglevel debug[/bold] to see the full error."
        )
        os._exit(1)

    # Zip up the app.
    if zip:
        if os.name == "posix":
            posix_export(backend, frontend)
        if os.name == "nt":
            nt_export(backend, frontend)


def nt_export(backend: bool = True, frontend: bool = True):
    """Export for nt (Windows) systems.

    Args:
        backend: Whether to zip up the backend app.
        frontend: Whether to zip up the frontend app.
    """
    cmd = r""
    if frontend:
        cmd = r'''powershell -Command "Set-Location .web/_static; Compress-Archive -Path .\* -DestinationPath ..\..\frontend.zip -Force"'''
        os.system(cmd)
    if backend:
        cmd = r'''powershell -Command "Get-ChildItem -File | Where-Object { $_.Name -notin @('.web', 'assets', 'frontend.zip', 'backend.zip') } | Compress-Archive -DestinationPath backend.zip -Update"'''
        os.system(cmd)


def posix_export(backend: bool = True, frontend: bool = True):
    """Export for posix (Linux, OSX) systems.

    Args:
        backend: Whether to zip up the backend app.
        frontend: Whether to zip up the frontend app.
    """
    cmd = r""
    if frontend:
        cmd = r"cd .web/_static && zip -r ../../frontend.zip ./*"
        os.system(cmd)
    if backend:
        cmd = r"zip -r backend.zip ./* -x .web/\* ./assets\* ./frontend.zip\* ./backend.zip\*"
        os.system(cmd)


def setup_frontend(
    root: Path,
    loglevel: constants.LogLevel = constants.LogLevel.ERROR,
    disable_telemetry: bool = True,
):
    """Set up the frontend.

    Args:
        root: The root path of the project.
        loglevel: The log level to use.
        disable_telemetry: Whether to disable the Next telemetry.
    """
    # Validate bun version.
    prerequisites.validate_and_install_bun(initialize=False)

    # Initialize the web directory if it doesn't exist.
    web_dir = prerequisites.create_web_directory(root)

    # Install frontend packages.
    prerequisites.install_frontend_packages(web_dir)

    # Copy asset files to public folder.
    path_ops.cp(
        src=str(root / constants.APP_ASSETS_DIR),
        dest=str(root / constants.WEB_ASSETS_DIR),
    )

    # set the environment variables in client(env.json)
    set_environment_variables()

    # Disable the Next telemetry.
    if disable_telemetry:
        new_process(
            [
                prerequisites.get_package_manager(),
                "run",
                "next",
                "telemetry",
                "disable",
            ],
            cwd=constants.WEB_DIR,
            stdout=subprocess.DEVNULL,
        )


def setup_frontend_prod(
    root: Path,
    loglevel: constants.LogLevel = constants.LogLevel.ERROR,
    disable_telemetry: bool = True,
):
    """Set up the frontend for prod mode.

    Args:
        root: The root path of the project.
        loglevel: The log level to use.
        disable_telemetry: Whether to disable the Next telemetry.
    """
    setup_frontend(root, loglevel, disable_telemetry)
    export_app(loglevel=loglevel, deploy_url=get_config().deploy_url)
