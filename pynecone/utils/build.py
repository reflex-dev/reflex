"""Building the app and initializing all prerequisites."""

from __future__ import annotations

import json
import os
import random
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, Optional, Union

from rich.progress import Progress

from pynecone import constants
from pynecone.config import get_config
from pynecone.utils import path_ops, prerequisites

if TYPE_CHECKING:
    from pynecone.app import App


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


def set_pynecone_project_hash():
    """Write the hash of the Pynecone project to a PCVERSION_APP_FILE."""
    update_json_file(
        constants.PCVERSION_APP_FILE, {"project_hash": random.getrandbits(128)}
    )


def set_environment_variables():
    """Write the upload url to a PCVERSION_APP_FILE."""
    update_json_file(
        constants.ENV_JSON,
        {
            "uploadUrl": constants.Endpoint.UPLOAD.get_url(),
            "eventUrl": constants.Endpoint.EVENT.get_url(),
            "pingUrl": constants.Endpoint.PING.get_url(),
        },
    )


def generate_sitemap(deploy_url: str):
    """Generate the sitemap config file.

    Args:
        deploy_url: The URL of the deployed app.
    """
    # Import here to avoid circular imports.
    from pynecone.compiler import templates

    config = json.dumps(
        {
            "siteUrl": deploy_url,
            "generateRobotsTxt": True,
        }
    )

    with open(constants.SITEMAP_CONFIG_FILE, "w") as f:
        f.write(templates.SITEMAP_CONFIG(config=config))


def export_app(
    app: App,
    backend: bool = True,
    frontend: bool = True,
    zip: bool = False,
    deploy_url: Optional[str] = None,
    loglevel: constants.LogLevel = constants.LogLevel.ERROR,
):
    """Zip up the app for deployment.

    Args:
        app: The app.
        backend: Whether to zip up the backend app.
        frontend: Whether to zip up the frontend app.
        zip: Whether to zip the app.
        deploy_url: The URL of the deployed app.
        loglevel: The log level to use.
    """
    # Remove the static folder.
    path_ops.rm(constants.WEB_STATIC_DIR)

    # Generate the sitemap file.
    if deploy_url is not None:
        generate_sitemap(deploy_url)

    # Create a progress object
    progress = Progress()

    # Add a single task to the progress object
    task = progress.add_task("Building app... ", total=500)

    # Start the progress bar
    with progress:
        # Run the subprocess command
        export_process = subprocess.Popen(
            [prerequisites.get_package_manager(), "run", "export"],
            cwd=constants.WEB_DIR,
            env=os.environ,
            stderr=subprocess.STDOUT,
            stdout=subprocess.PIPE,  # Redirect stdout to a pipe
            universal_newlines=True,  # Set universal_newlines to True for text mode
        )

        if export_process.stdout:
            for line in iter(export_process.stdout.readline, ""):
                if "Linting and checking " in line:
                    progress.update(task, advance=100)
                elif "Compiled successfully" in line:
                    progress.update(task, advance=100)
                elif "Route (pages)" in line:
                    progress.update(task, advance=100)
                elif "automatically rendered as static HTML" in line:
                    progress.update(task, advance=100)
                elif "Export successful" in line:
                    print("DOOE")
                    progress.update(task, completed=500)
                    break  # Exit the loop if the completion message is found
                elif loglevel == constants.LogLevel.DEBUG:
                    print(line, end="")

        # Wait for the subprocess to complete
        export_process.wait()
        print("Export process completed.")

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


def setup_frontend(root: Path, disable_telemetry: bool = True):
    """Set up the frontend.

    Args:
        root: root path of the project.
        disable_telemetry: Whether to disable the Next telemetry.
    """
    # Initialize the web directory if it doesn't exist.
    web_dir = prerequisites.create_web_directory(root)

    # Install frontend packages.
    prerequisites.install_frontend_packages(web_dir)

    # Copy asset files to public folder.
    path_ops.mkdir(str(root / constants.WEB_ASSETS_DIR))
    path_ops.cp(
        src=str(root / constants.APP_ASSETS_DIR),
        dest=str(root / constants.WEB_ASSETS_DIR),
    )

    # set the environment variables in client(env.json)
    set_environment_variables()

    # Disable the Next telemetry.
    if disable_telemetry:
        subprocess.Popen(
            [
                prerequisites.get_package_manager(),
                "run",
                "next",
                "telemetry",
                "disable",
            ],
            cwd=constants.WEB_DIR,
            env=os.environ,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.STDOUT,
        )


def setup_backend():
    """Set up backend.

    Specifically ensures backend database is updated when running --no-frontend.
    """
    # Import here to avoid circular imports.
    from pynecone.model import Model

    config = get_config()
    if config.db_url is not None:
        Model.create_all()
