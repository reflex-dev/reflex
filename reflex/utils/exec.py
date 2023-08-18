"""Everything regarding execution of the built app."""

from __future__ import annotations

import os
import platform
import sys
from pathlib import Path

from reflex import constants
from reflex.config import get_config
from reflex.utils import console, path_ops, prerequisites, processes
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
):
    """Run the process and launch the URL.

    Args:
        run_command: The command to run.
    """
    process = processes.new_process(
        run_command, cwd=constants.WEB_DIR, shell=constants.IS_WINDOWS
    )

    if process.stdout:
        for line in process.stdout:
            if "ready started server on" in line:
                url = line.split("url: ")[-1].strip()
                console.print(f"App running at: [bold green]{url}")
            else:
                console.debug(line)


def run_frontend(
    root: Path,
    port: str,
):
    """Run the frontend.

    Args:
        root: The root path of the project.
        port: The port to run the frontend on.
    """
    # Start watching asset folder.
    start_watching_assets_folder(root)

    # Run the frontend in development mode.
    console.rule("[bold green]App Running")
    os.environ["PORT"] = str(get_config().frontend_port if port is None else port)
    run_process_and_launch_url([prerequisites.get_package_manager(), "run", "dev"])


def run_frontend_prod(
    root: Path,
    port: str,
):
    """Run the frontend.

    Args:
        root: The root path of the project (to keep same API as run_frontend).
        port: The port to run the frontend on.
    """
    # Set the port.
    os.environ["PORT"] = str(get_config().frontend_port if port is None else port)

    # Run the frontend in production mode.
    console.rule("[bold green]App Running")
    run_process_and_launch_url([prerequisites.get_package_manager(), "run", "prod"])


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
    processes.new_process(
        [
            "uvicorn",
            f"{app_name}:{constants.APP_VAR}.{constants.API_VAR}",
            "--host",
            host,
            "--port",
            str(port),
            "--log-level",
            loglevel.value,
            "--reload",
            "--reload-dir",
            app_name.split(".")[0],
        ],
        run=True,
        show_logs=True,
    )


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
    config = get_config()
    RUN_BACKEND_PROD = f"gunicorn --worker-class uvicorn.workers.UvicornH11Worker --preload --timeout {config.timeout} --log-level critical".split()
    RUN_BACKEND_PROD_WINDOWS = f"uvicorn --timeout-keep-alive {config.timeout}".split()
    command = (
        [
            *RUN_BACKEND_PROD_WINDOWS,
            "--host",
            host,
            "--port",
            str(port),
            f"{app_name}:{constants.APP_VAR}",
        ]
        if constants.IS_WINDOWS
        else [
            *RUN_BACKEND_PROD,
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
    processes.new_process(command, run=True, show_logs=True)


def output_system_info():
    """Show system informations if the loglevel is in DEBUG."""
    if console.LOG_LEVEL > constants.LogLevel.DEBUG:
        return

    config = get_config()
    try:
        config_file = sys.modules[config.__module__].__file__
    except Exception:
        config_file = None

    console.rule(f"System Info")
    console.debug(f"Config file: {config_file!r}")
    console.debug(f"Config: {config}")

    dependencies = [
        f"[Reflex {constants.VERSION} with Python {platform.python_version()} (PATH: {sys.executable})]",
        f"[Node {prerequisites.get_node_version()} (Expected: {constants.NODE_VERSION}) (PATH:{constants.NODE_PATH})]",
    ]

    system = platform.system()

    if system != "Windows":
        dependencies.extend(
            [
                f"[NVM {constants.NVM_VERSION} (Expected: {constants.NVM_VERSION}) (PATH: {constants.NVM_PATH})]",
                f"[Bun {prerequisites.get_bun_version()} (Expected: {constants.BUN_VERSION}) (PATH: {config.bun_path})]",
            ],
        )
    else:
        dependencies.append(
            f"[FNM {constants.FNM_VERSION} (Expected: {constants.FNM_VERSION}) (PATH: {constants.FNM_EXE})]",
        )

    if system == "Linux":
        import distro  # type: ignore

        os_version = distro.name(pretty=True)
    else:
        os_version = platform.version()

    dependencies.append(f"[OS {platform.system()} {os_version}]")

    for dep in dependencies:
        console.debug(f"{dep}")

    console.debug(
        f"Using package installer at: {prerequisites.get_install_package_manager()}"
    )
    console.debug(f"Using package executer at: {prerequisites.get_package_manager()}")
    if system != "Windows":
        console.debug(f"Unzip path: {path_ops.which('unzip')}")
