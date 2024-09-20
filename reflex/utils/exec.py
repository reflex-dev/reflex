"""Everything regarding execution of the built app."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import urljoin

import psutil

from reflex import constants
from reflex.config import get_config
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
                            console.print(
                                f"Backend running at: [bold green]http://0.0.0.0:{get_config().backend_port}[/bold green]"
                            )
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
    import uvicorn

    config = get_config()
    app_module = f"reflex.app_module_for_backend:{constants.CompileVars.APP}"

    web_dir = get_web_dir()
    # Create a .nocompile file to skip compile for backend.
    if web_dir.exists():
        (web_dir / constants.NOCOMPILE_FILE).touch()

    # Run the backend in development mode.
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
    from reflex.utils import processes

    config = get_config()
    num_workers = (
        processes.get_num_workers()
        if not config.gunicorn_workers
        else config.gunicorn_workers
    )
    RUN_BACKEND_PROD = f"gunicorn --worker-class {config.gunicorn_worker_class} --preload --timeout {config.timeout} --log-level critical".split()
    RUN_BACKEND_PROD_WINDOWS = f"uvicorn --timeout-keep-alive {config.timeout}".split()
    app_module = f"reflex.app_module_for_backend:{constants.CompileVars.APP}"
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

    from reflex.utils import prerequisites

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
        f"Using package installer at: {prerequisites.get_install_package_manager()}"  # type: ignore
    )
    console.debug(f"Using package executer at: {prerequisites.get_package_manager()}")  # type: ignore
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
    current_mode = os.environ.get(
        constants.ENV_MODE_ENV_VAR,
        constants.Env.DEV.value,
    )
    return current_mode == constants.Env.PROD.value


def should_skip_compile() -> bool:
    """Whether the app should skip compile.

    Returns:
        True if the app should skip compile.
    """
    return os.environ.get(constants.SKIP_COMPILE_ENV_VAR) == "yes"
