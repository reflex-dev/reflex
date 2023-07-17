"""Everything regarding execution of the built app."""

from __future__ import annotations

import os
import platform
import subprocess
from pathlib import Path

from rich import print

from reflex import constants
from reflex.config import get_config
from reflex.utils import console, prerequisites, processes
from reflex.utils.processes import new_process
from reflex.utils.watch import AssetFolderWatch


def start_watching_assets_folder(root):
    """Start watching assets folder.

    Args:
        root: root path of the project.
    """
    asset_watch = AssetFolderWatch(root)
    asset_watch.start()


def run_process_and_launch_url(
    run_command: list[str],
    loglevel: constants.LogLevel = constants.LogLevel.ERROR,
):
    """Run the process and launch the URL.

    Args:
        run_command: The command to run.
        loglevel: The log level to use.
    """
    process = new_process(
        run_command,
        cwd=constants.WEB_DIR,
    )

    if process.stdout:
        for line in process.stdout:
            if "ready started server on" in line:
                url = line.split("url: ")[-1].strip()
                print(f"App running at: [bold green]{url}")
            if loglevel == constants.LogLevel.DEBUG:
                print(line, end="")


def run_frontend(
    root: Path,
    port: str,
    loglevel: constants.LogLevel = constants.LogLevel.ERROR,
):
    """Run the frontend.

    Args:
        root: The root path of the project.
        port: The port to run the frontend on.
        loglevel: The log level to use.
    """
    # Start watching asset folder.
    start_watching_assets_folder(root)

    # Run the frontend in development mode.
    console.rule("[bold green]App Running")
    os.environ["PORT"] = get_config().frontend_port if port is None else port
    run_process_and_launch_url(
        [prerequisites.get_package_manager(), "run", "dev"], loglevel
    )


def run_frontend_prod(
    root: Path,
    port: str,
    loglevel: constants.LogLevel = constants.LogLevel.ERROR,
):
    """Run the frontend.

    Args:
        root: The root path of the project (to keep same API as run_frontend).
        port: The port to run the frontend on.
        loglevel: The log level to use.
    """
    # Set the port.
    os.environ["PORT"] = get_config().frontend_port if port is None else port

    # Run the frontend in production mode.
    console.rule("[bold green]App Running")
    run_process_and_launch_url(
        [prerequisites.get_package_manager(), "run", "prod"], loglevel
    )


def run_backend(
    app_name: str,
    host: str,
    port: int,
    loglevel: constants.LogLevel = constants.LogLevel.ERROR,
):
    """Run the backend.

    Args:
        host: The app host
        app_name: The app name.
        port: The app port
        loglevel: The log level.
    """
    cmd = [
        "uvicorn",
        f"{app_name}:{constants.APP_VAR}.{constants.API_VAR}",
        "--host",
        host,
        "--port",
        str(port),
        "--log-level",
        loglevel,
        "--reload",
        "--reload-dir",
        app_name.split(".")[0],
    ]
    process = subprocess.Popen(cmd)

    try:
        process.wait()
    except KeyboardInterrupt:
        process.terminate()


def run_backend_prod(
    app_name: str,
    host: str,
    port: int,
    loglevel: constants.LogLevel = constants.LogLevel.ERROR,
):
    """Run the backend.

    Args:
        host: The app host
        app_name: The app name.
        port: The app port
        loglevel: The log level.
    """
    num_workers = processes.get_num_workers()
    command = (
        [
            *constants.RUN_BACKEND_PROD_WINDOWS,
            "--host",
            host,
            "--port",
            str(port),
            f"{app_name}:{constants.APP_VAR}",
        ]
        if platform.system() == "Windows"
        else [
            *constants.RUN_BACKEND_PROD,
            "--bind",
            f"{host}:{port}",
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
