"""Everything regarding execution of the built app."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import sys
from pathlib import Path
from urllib.parse import urljoin

import psutil
import uvicorn

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


def detect_package_change(json_file_path: str) -> str:
    """Calculates the SHA-256 hash of a JSON file and returns it as a hexadecimal string.

    Args:
        json_file_path (str): The path to the JSON file to be hashed.

    Returns:
        str: The SHA-256 hash of the JSON file as a hexadecimal string.

    Example:
        >>> detect_package_change("package.json")
        'a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2w3x4y5z6a7b8c9d0e1f2'
    """
    with open(json_file_path, "r") as file:
        json_data = json.load(file)

    # Calculate the hash
    json_string = json.dumps(json_data, sort_keys=True)
    hash_object = hashlib.sha256(json_string.encode())
    return hash_object.hexdigest()


def kill(proc_pid: int):
    """Kills a process and all its child processes.

    Args:
        proc_pid (int): The process ID of the process to be killed.

    Example:
        >>> kill(1234)
    """
    process = psutil.Process(proc_pid)
    for proc in process.children(recursive=True):
        proc.kill()
    process.kill()


def run_process_and_launch_url(run_command: list[str]):
    """Run the process and launch the URL.

    Args:
        run_command: The command to run.
    """
    json_file_path = os.path.join(constants.Dirs.WEB, "package.json")
    last_hash = detect_package_change(json_file_path)
    process = None
    first_run = True

    while True:
        if process is None:
            process = processes.new_process(
                run_command, cwd=constants.Dirs.WEB, shell=constants.IS_WINDOWS
            )
        if process.stdout:
            for line in processes.stream_logs("Starting frontend", process):
                match = re.search(constants.Next.FRONTEND_LISTENING_REGEX, line)
                if match:
                    if first_run:
                        url = match.group(1)
                        if get_config().frontend_path != "":
                            url = urljoin(url, get_config().frontend_path)
                        console.print(f"App running at: [bold green]{url}")
                        first_run = False
                    else:
                        console.print("New packages detected: Updating app...")
                else:
                    new_hash = detect_package_change(json_file_path)
                    if new_hash != last_hash:
                        last_hash = new_hash
                        kill(process.pid)
                        process = None
                        break  # for line in process.stdout
        if process is not None:
            break  # while True


def run_frontend(root: Path, port: str):
    """Run the frontend.

    Args:
        root: The root path of the project.
        port: The port to run the frontend on.
    """
    # Start watching asset folder.
    start_watching_assets_folder(root)
    # validate dependencies before run
    prerequisites.validate_frontend_dependencies(init=False)

    # Run the frontend in development mode.
    console.rule("[bold green]App Running")
    os.environ["PORT"] = str(get_config().frontend_port if port is None else port)
    run_process_and_launch_url([prerequisites.get_package_manager(), "run", "dev"])  # type: ignore


def run_frontend_prod(root: Path, port: str):
    """Run the frontend.

    Args:
        root: The root path of the project (to keep same API as run_frontend).
        port: The port to run the frontend on.
    """
    # Set the port.
    os.environ["PORT"] = str(get_config().frontend_port if port is None else port)
    # validate dependencies before run
    prerequisites.validate_frontend_dependencies(init=False)
    # Run the frontend in production mode.
    console.rule("[bold green]App Running")
    run_process_and_launch_url([prerequisites.get_package_manager(), "run", "prod"])  # type: ignore


def run_backend(
    host: str,
    port: int,
    loglevel: constants.LogLevel = constants.LogLevel.ERROR,
):
    """Run the backend.

    Args:
        host: The app host
        port: The app port
        loglevel: The log level.
    """
    config = get_config()
    app_module = f"{config.app_name}.{config.app_name}:{constants.CompileVars.APP}"
    uvicorn.run(
        app=f"{app_module}.{constants.CompileVars.API}",
        host=host,
        port=port,
        log_level=loglevel.value,
        reload=True,
        reload_dirs=[config.app_name],
    )


def run_backend_prod(
    host: str,
    port: int,
    loglevel: constants.LogLevel = constants.LogLevel.ERROR,
):
    """Run the backend.

    Args:
        host: The app host
        port: The app port
        loglevel: The log level.
    """
    num_workers = processes.get_num_workers()
    config = get_config()
    RUN_BACKEND_PROD = f"gunicorn --worker-class uvicorn.workers.UvicornH11Worker --preload --timeout {config.timeout} --log-level critical".split()
    RUN_BACKEND_PROD_WINDOWS = f"uvicorn --timeout-keep-alive {config.timeout}".split()
    app_module = f"{config.app_name}.{config.app_name}:{constants.CompileVars.APP}"
    command = (
        [
            *RUN_BACKEND_PROD_WINDOWS,
            "--host",
            host,
            "--port",
            str(port),
            app_module,
        ]
        if constants.IS_WINDOWS
        else [
            *RUN_BACKEND_PROD,
            "--bind",
            f"{host}:{port}",
            "--threads",
            str(num_workers),
            f"{app_module}()",
        ]
    )

    command += [
        "--log-level",
        loglevel.value,
        "--workers",
        str(num_workers),
    ]
    processes.new_process(
        command,
        run=True,
        show_logs=True,
        env={constants.SKIP_COMPILE_ENV_VAR: "yes"},  # skip compile for prod backend
    )


def output_system_info():
    """Show system information if the loglevel is in DEBUG."""
    if console._LOG_LEVEL > constants.LogLevel.DEBUG:
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
        f"[Reflex {constants.Reflex.VERSION} with Python {platform.python_version()} (PATH: {sys.executable})]",
        f"[Node {prerequisites.get_node_version()} (Expected: {constants.Node.VERSION}) (PATH:{path_ops.get_node_path()})]",
    ]

    system = platform.system()

    if system != "Windows":
        dependencies.extend(
            [
                f"[FNM {constants.Fnm.VERSION} (Expected: {constants.Fnm.VERSION}) (PATH: {constants.Fnm.EXE})]",
                f"[Bun {prerequisites.get_bun_version()} (Expected: {constants.Bun.VERSION}) (PATH: {config.bun_path})]",
            ],
        )
    else:
        dependencies.append(
            f"[FNM {constants.Fnm.VERSION} (Expected: {constants.Fnm.VERSION}) (PATH: {constants.Fnm.EXE})]",
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
        f"Using package installer at: {prerequisites.get_install_package_manager()}"  # type: ignore
    )
    console.debug(f"Using package executer at: {prerequisites.get_package_manager()}")  # type: ignore
    if system != "Windows":
        console.debug(f"Unzip path: {path_ops.which('unzip')}")
