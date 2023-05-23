"""Everything regarding execution of the built app."""

from __future__ import annotations

import os
import platform
import subprocess
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from rich import print

from pynecone import constants
from pynecone.config import get_config
from pynecone.utils import console, prerequisites, processes
from pynecone.utils.build import export_app, setup_backend, setup_frontend
from pynecone.utils.watch import AssetFolderWatch

if TYPE_CHECKING:
    from pynecone.app import App


def start_watching_assets_folder(root):
    """Start watching assets folder.

    Args:
        root: root path of the project.
    """
    asset_watch = AssetFolderWatch(root)
    asset_watch.start()


def run_process_and_launch_url(
    run_command: list[str],
    root: Path,
    loglevel: constants.LogLevel = constants.LogLevel.ERROR,
):
    """Run the process and launch the URL.

    Args:
        run_command: The command to run.
        root: root path of the project.
        loglevel: The log level to use.
    """
    process = subprocess.Popen(
        run_command,
        cwd=constants.WEB_DIR,
        env=os.environ,
        stderr=subprocess.STDOUT,
        stdout=subprocess.PIPE,
        universal_newlines=True,
    )

    current_time = datetime.now()
    if process.stdout:
        for line in process.stdout:
            if "ready started server on" in line:
                url = line.split("url: ")[-1].strip()
                print(f"App running at: [bold green]{url}")
            if (
                "Fast Refresh" in line
                and (datetime.now() - current_time).total_seconds() > 1
            ):
                print(
                    f"[yellow][Updating App][/yellow] Applying changes and refreshing. Time: {current_time}"
                )
                current_time = datetime.now()
            elif loglevel == constants.LogLevel.DEBUG:
                print(line, end="")


def run_frontend(
    app: App,
    root: Path,
    port: str,
    loglevel: constants.LogLevel = constants.LogLevel.ERROR,
):
    """Run the frontend.

    Args:
        app: The app.
        root: root path of the project.
        port: port of the app.
        loglevel: The log level to use.
    """
    # validate bun version
    prerequisites.validate_and_install_bun(initialize=False)

    # Set up the frontend.
    setup_frontend(root)

    # Start watching asset folder.
    start_watching_assets_folder(root)

    # Run the frontend in development mode.
    console.rule("[bold green]App Running")
    os.environ["PORT"] = get_config().port if port is None else port
    run_process_and_launch_url(
        [prerequisites.get_package_manager(), "run", "dev"], root, loglevel
    )


def run_frontend_prod(
    app: App,
    root: Path,
    port: str,
    loglevel: constants.LogLevel = constants.LogLevel.ERROR,
):
    """Run the frontend.

    Args:
        app: The app.
        root: root path of the project.
        port: port of the app.
        loglevel: The log level to use.
    """
    # Set up the frontend.
    setup_frontend(root)

    # Export the app.
    export_app(app, loglevel=loglevel)

    # Set the port.
    os.environ["PORT"] = get_config().port if port is None else port

    # Run the frontend in production mode.
    console.rule("[bold green]App Running")
    run_process_and_launch_url(
        [prerequisites.get_package_manager(), "run", "prod"], root, loglevel
    )


def run_backend(
    app_name: str, port: int, loglevel: constants.LogLevel = constants.LogLevel.ERROR
):
    """Run the backend.

    Args:
        app_name: The app name.
        port: The app port
        loglevel: The log level.
    """
    setup_backend()

    cmd = [
        "uvicorn",
        f"{app_name}:{constants.APP_VAR}.{constants.API_VAR}",
        "--host",
        constants.BACKEND_HOST,
        "--port",
        str(port),
        "--log-level",
        loglevel,
        "--reload",
    ]
    process = subprocess.Popen(cmd)

    try:
        process.wait()
    except KeyboardInterrupt:
        process.terminate()


def run_backend_prod(
    app_name: str, port: int, loglevel: constants.LogLevel = constants.LogLevel.ERROR
):
    """Run the backend.

    Args:
        app_name: The app name.
        port: The app port
        loglevel: The log level.
    """
    setup_backend()

    num_workers = processes.get_num_workers()
    command = (
        [
            *constants.RUN_BACKEND_PROD_WINDOWS,
            "--host",
            "0.0.0.0",
            "--port",
            str(port),
            f"{app_name}:{constants.APP_VAR}",
        ]
        if platform.system() == "Windows"
        else [
            *constants.RUN_BACKEND_PROD,
            "--bind",
            f"0.0.0.0:{port}",
            "--threads",
            str(num_workers),
            f"{app_name}:{constants.APP_VAR}()",
        ]
    )

    command += [
        "--log-level",
        loglevel.value,
        "--workers",
        str(num_workers),
    ]
    subprocess.run(command)
