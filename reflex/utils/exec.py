"""Everything regarding execution of the built app."""

from __future__ import annotations

from abc import abstractmethod, ABCMeta
from typing import IO, Any, Literal, Sequence, Type

import hashlib
import json
import os
import platform
import re
import subprocess
import sys
import asyncio
import ssl
from configparser import RawConfigParser
from pathlib import Path
from urllib.parse import urljoin
from pydantic import Field
from dataclasses import dataclass

import psutil

from reflex import constants, server
from reflex.base import Base
from reflex.config import environment, get_config
from reflex.constants.base import LogLevel
from reflex.utils import console, path_ops
from reflex.utils.prerequisites import get_web_dir

# For uvicorn windows bug fix (#2335)
frontend_process = None


def detect_package_change(json_file_path: str) -> str:
    """Calculates the SHA-256 hash of a JSON file and returns it as a hexadecimal string.

    Args:
        json_file_path: The path to the JSON file to be hashed.

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


def notify_backend():
    """Output a string notifying where the backend is running."""
    console.print(
        f"Backend running at: [bold green]http://0.0.0.0:{get_config().backend_port}[/bold green]"
    )


# run_process_and_launch_url is assumed to be used
# only to launch the frontend
# If this is not the case, might have to change the logic
def run_process_and_launch_url(run_command: list[str], backend_present=True):
    """Run the process and launch the URL.

    Args:
        run_command: The command to run.
        backend_present: Whether the backend is present.
    """
    from reflex.utils import processes

    json_file_path = get_web_dir() / constants.PackageJson.PATH
    last_hash = detect_package_change(str(json_file_path))
    process = None
    first_run = True

    while True:
        if process is None:
            kwargs = {}
            if constants.IS_WINDOWS and backend_present:
                kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP  # type: ignore
            process = processes.new_process(
                run_command,
                cwd=get_web_dir(),
                shell=constants.IS_WINDOWS,
                **kwargs,
            )
            global frontend_process
            frontend_process = process
        if process.stdout:
            for line in processes.stream_logs("Starting frontend", process):
                match = re.search(constants.Next.FRONTEND_LISTENING_REGEX, line)
                if match:
                    if first_run:
                        url = match.group(1)
                        if get_config().frontend_path != "":
                            url = urljoin(url, get_config().frontend_path)

                        console.print(
                            f"App running at: [bold green]{url}[/bold green]{' (Frontend-only mode)' if not backend_present else ''}"
                        )
                        if backend_present:
                            notify_backend()
                        first_run = False
                    else:
                        console.print("New packages detected: Updating app...")
                else:
                    if any(
                        [x in line for x in ("bin executable does not exist on disk",)]
                    ):
                        console.error(
                            "Try setting `REFLEX_USE_NPM=1` and re-running `reflex init` and `reflex run` to use npm instead of bun:\n"
                            "`REFLEX_USE_NPM=1 reflex init`\n"
                            "`REFLEX_USE_NPM=1 reflex run`"
                        )
                    new_hash = detect_package_change(str(json_file_path))
                    if new_hash != last_hash:
                        last_hash = new_hash
                        kill(process.pid)
                        process = None
                        break  # for line in process.stdout
        if process is not None:
            break  # while True


def run_frontend(root: Path, port: str, backend_present=True):
    """Run the frontend.

    Args:
        root: The root path of the project.
        port: The port to run the frontend on.
        backend_present: Whether the backend is present.
    """
    from reflex.utils import prerequisites

    # validate dependencies before run
    prerequisites.validate_frontend_dependencies(init=False)

    # Run the frontend in development mode.
    console.rule("[bold green]App Running")
    os.environ["PORT"] = str(get_config().frontend_port if port is None else port)
    run_process_and_launch_url(
        [prerequisites.get_package_manager(), "run", "dev"],  # type: ignore
        backend_present,
    )


def run_frontend_prod(root: Path, port: str, backend_present=True):
    """Run the frontend.

    Args:
        root: The root path of the project (to keep same API as run_frontend).
        port: The port to run the frontend on.
        backend_present: Whether the backend is present.
    """
    from reflex.utils import prerequisites

    # Set the port.
    os.environ["PORT"] = str(get_config().frontend_port if port is None else port)
    # validate dependencies before run
    prerequisites.validate_frontend_dependencies(init=False)
    # Run the frontend in production mode.
    console.rule("[bold green]App Running")
    run_process_and_launch_url(
        [prerequisites.get_package_manager(), "run", "prod"],  # type: ignore
        backend_present,
    )


def should_use_granian():
    """Whether to use Granian for backend.

    Returns:
        True if Granian should be used.
    """
    return environment.REFLEX_USE_GRANIAN.get()


def get_app_module():
    """Get the app module for the backend.

    Returns:
        The app module for the backend.
    """
    return f"reflex.app_module_for_backend:{constants.CompileVars.APP}"
### REWORK <--


def get_granian_target():
    """Get the Granian target for the backend.

    Returns:
        The Granian target for the backend.
    """
    import reflex

    app_module_path = Path(reflex.__file__).parent / "app_module_for_backend.py"

    return f"{str(app_module_path)}:{constants.CompileVars.APP}.{constants.CompileVars.API}"


def run_backend(
    host: str,
    port: int,
    loglevel: constants.LogLevel = constants.LogLevel.ERROR,
    frontend_present: bool = False,
):
    """Run the backend.

    Args:
        host: The app host
        port: The app port
        loglevel: The log level.
        frontend_present: Whether the frontend is present.
    """
    web_dir = get_web_dir()
    # Create a .nocompile file to skip compile for backend.
    if web_dir.exists():
        (web_dir / constants.NOCOMPILE_FILE).touch()

    if not frontend_present:
        notify_backend()

    # Run the backend in development mode.
    if should_use_granian():
        run_granian_backend(host, port, loglevel)
    else:
        run_uvicorn_backend(host, port, loglevel)


def run_uvicorn_backend(host, port, loglevel: LogLevel):
    """Run the backend in development mode using Uvicorn.

    Args:
        host: The app host
        port: The app port
        loglevel: The log level.
    """
    import uvicorn

    uvicorn.run(
        app=f"{get_app_module()}.{constants.CompileVars.API}",
        host=host,
        port=port,
        log_level=loglevel.value,
        reload=True,
        reload_dirs=[get_config().app_name],
    )


def run_granian_backend(host, port, loglevel: LogLevel):
    """Run the backend in development mode using Granian.

    Args:
        host: The app host
        port: The app port
        loglevel: The log level.
    """
    console.debug("Using Granian for backend")
    try:
        from granian import Granian  # type: ignore
        from granian.constants import Interfaces  # type: ignore
        from granian.log import LogLevels  # type: ignore

        Granian(
            target=get_granian_target(),
            address=host,
            port=port,
            interface=Interfaces.ASGI,
            log_level=LogLevels(loglevel.value),
            reload=True,
            reload_paths=[Path(get_config().app_name)],
            reload_ignore_dirs=[".web"],
        ).serve()
    except ImportError:
        console.error(
            'InstallError: REFLEX_USE_GRANIAN is set but `granian` is not installed. (run `pip install "granian[reload]>=1.6.0"`)'
        )
        os._exit(1)


def _get_backend_workers():
    from reflex.utils import processes

    config = get_config()
    return (
        processes.get_num_workers()
        if not config.gunicorn_workers
        else config.gunicorn_workers
    )


def run_backend_prod(
    host: str,
    port: int,
    loglevel: constants.LogLevel = constants.LogLevel.ERROR,
    frontend_present: bool = False,
):
    """Run the backend.

    Args:
        host: The app host
        port: The app port
        loglevel: The log level.
        frontend_present: Whether the frontend is present.
    """
    print("[reflex.utils.exec::run_backend_prod] start")
    if not frontend_present:
        notify_backend()

    config = get_config()

    if should_use_granian():
        run_granian_backend_prod(host, port, loglevel)
    else:
        from reflex.utils import processes

        backend_server_prod = config.backend_server_prod
        if isinstance(backend_server_prod, server.GunicornBackendServer):
            backend_server_prod.app = f"{get_app_module()}()"
            backend_server_prod.preload_app = True
            backend_server_prod.loglevel = loglevel.value  # type: ignore
            backend_server_prod.bind = [f"{host}:{port}"]
            backend_server_prod.threads = _get_backend_workers()
            backend_server_prod.workers = _get_backend_workers()

        print(backend_server_prod.run_prod())
        processes.new_process(
            backend_server_prod.run_prod(),
            run=True,
            show_logs=True,
            env={
                environment.REFLEX_SKIP_COMPILE.name: "true"
            },  # skip compile for prod backend
        )
        print("[reflex.utils.exec::run_backend_prod] done")


def run_granian_backend_prod(host, port, loglevel):
    """Run the backend in production mode using Granian.

    Args:
        host: The app host
        port: The app port
        loglevel: The log level.
    """
    from reflex.utils import processes

    try:
        from granian.constants import Interfaces  # type: ignore

        command = [
            "granian",
            "--workers",
            str(_get_backend_workers()),
            "--log-level",
            "critical",
            "--host",
            host,
            "--port",
            str(port),
            "--interface",
            str(Interfaces.ASGI),
            get_granian_target(),
        ]
        processes.new_process(
            command,
            run=True,
            show_logs=True,
            env={
                environment.REFLEX_SKIP_COMPILE.name: "true"
            },  # skip compile for prod backend
        )
    except ImportError:
        console.error(
            'InstallError: REFLEX_USE_GRANIAN is set but `granian` is not installed. (run `pip install "granian[reload]>=1.6.0"`)'
        )


### REWORK-->
def output_system_info():
    """Show system information if the loglevel is in DEBUG."""
    if console._LOG_LEVEL > constants.LogLevel.DEBUG:
        return

    from reflex.utils import prerequisites

    config = get_config()
    try:
        config_file = sys.modules[config.__module__].__file__
    except Exception:
        config_file = None

    console.rule("System Info")
    console.debug(f"Config file: {config_file!r}")
    console.debug(f"Config: {config}")

    dependencies = [
        f"[Reflex {constants.Reflex.VERSION} with Python {platform.python_version()} (PATH: {sys.executable})]",
        f"[Node {prerequisites.get_node_version()} (Expected: {constants.Node.VERSION}) (PATH:{path_ops.get_node_path()})]",
    ]

    system = platform.system()

    if (
        system != "Windows"
        or system == "Windows"
        and prerequisites.is_windows_bun_supported()
    ):
        dependencies.extend(
            [
                f"[FNM {prerequisites.get_fnm_version()} (Expected: {constants.Fnm.VERSION}) (PATH: {constants.Fnm.EXE})]",
                f"[Bun {prerequisites.get_bun_version()} (Expected: {constants.Bun.VERSION}) (PATH: {config.bun_path})]",
            ],
        )
    else:
        dependencies.append(
            f"[FNM {prerequisites.get_fnm_version()} (Expected: {constants.Fnm.VERSION}) (PATH: {constants.Fnm.EXE})]",
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
        f"Using package installer at: {prerequisites.get_install_package_manager(on_failure_return_none=True)}"  # type: ignore
    )
    console.debug(
        f"Using package executer at: {prerequisites.get_package_manager(on_failure_return_none=True)}"
    )  # type: ignore
    if system != "Windows":
        console.debug(f"Unzip path: {path_ops.which('unzip')}")


def is_testing_env() -> bool:
    """Whether the app is running in a testing environment.

    Returns:
        True if the app is running in under pytest.
    """
    return constants.PYTEST_CURRENT_TEST in os.environ


def is_prod_mode() -> bool:
    """Check if the app is running in production mode.

    Returns:
        True if the app is running in production mode or False if running in dev mode.
    """
    current_mode = environment.REFLEX_ENV_MODE.get()
    return current_mode == constants.Env.PROD


def is_frontend_only() -> bool:
    """Check if the app is running in frontend-only mode.

    Returns:
        True if the app is running in frontend-only mode.
    """
    console.deprecate(
        "is_frontend_only() is deprecated and will be removed in a future release.",
        reason="Use `environment.REFLEX_FRONTEND_ONLY.get()` instead.",
        deprecation_version="0.6.5",
        removal_version="0.7.0",
    )
    return environment.REFLEX_FRONTEND_ONLY.get()


def is_backend_only() -> bool:
    """Check if the app is running in backend-only mode.

    Returns:
        True if the app is running in backend-only mode.
    """
    console.deprecate(
        "is_backend_only() is deprecated and will be removed in a future release.",
        reason="Use `environment.REFLEX_BACKEND_ONLY.get()` instead.",
        deprecation_version="0.6.5",
        removal_version="0.7.0",
    )
    return environment.REFLEX_BACKEND_ONLY.get()


def should_skip_compile() -> bool:
    """Whether the app should skip compile.

    Returns:
        True if the app should skip compile.
    """
    console.deprecate(
        "should_skip_compile() is deprecated and will be removed in a future release.",
        reason="Use `environment.REFLEX_SKIP_COMPILE.get()` instead.",
        deprecation_version="0.6.5",
        removal_version="0.7.0",
    )
    return environment.REFLEX_SKIP_COMPILE.get()


### REWORK <--
