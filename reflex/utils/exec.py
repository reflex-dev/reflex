"""Everything regarding execution of the built app."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import platform
import re
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any, NamedTuple, TypedDict
from urllib.parse import urljoin

from reflex import constants
from reflex.config import get_config
from reflex.constants.base import LogLevel
from reflex.environment import environment
from reflex.utils import console, path_ops
from reflex.utils.decorator import once
from reflex.utils.misc import get_module_path
from reflex.utils.prerequisites import get_web_dir

# For uvicorn windows bug fix (#2335)
frontend_process = None


def get_package_json_and_hash(package_json_path: Path) -> tuple[PackageJson, str]:
    """Get the content of package.json and its hash.

    Args:
        package_json_path: The path to the package.json file.

    Returns:
        A tuple containing the content of package.json as a dictionary and its SHA-256 hash.
    """
    with package_json_path.open("r") as file:
        json_data = json.load(file)

    # Calculate the hash
    json_string = json.dumps(json_data, sort_keys=True)
    hash_object = hashlib.sha256(json_string.encode())
    return (json_data, hash_object.hexdigest())


class PackageJson(TypedDict):
    """package.json content."""

    dependencies: dict[str, str]
    devDependencies: dict[str, str]


class Change(NamedTuple):
    """A named tuple to represent a change in package dependencies."""

    added: set[str]
    removed: set[str]


def format_change(name: str, change: Change) -> str:
    """Format the change for display.

    Args:
        name: The name of the change (e.g., "dependencies" or "devDependencies").
        change: The Change named tuple containing added and removed packages.

    Returns:
        A formatted string representing the changes.
    """
    if not change.added and not change.removed:
        return ""
    added_str = ", ".join(sorted(change.added))
    removed_str = ", ".join(sorted(change.removed))
    change_str = f"{name}:\n"
    if change.added:
        change_str += f"  Added: {added_str}\n"
    if change.removed:
        change_str += f"  Removed: {removed_str}\n"
    return change_str.strip()


def get_different_packages(
    old_package_json_content: PackageJson,
    new_package_json_content: PackageJson,
) -> tuple[Change, Change]:
    """Get the packages that are different between two package JSON contents.

    Args:
        old_package_json_content: The content of the old package JSON.
        new_package_json_content: The content of the new package JSON.

    Returns:
        A tuple containing two `Change` named tuples:
        - The first `Change` contains the changes in the `dependencies` section.
        - The second `Change` contains the changes in the `devDependencies` section.
    """

    def get_changes(old: dict[str, str], new: dict[str, str]) -> Change:
        """Get the changes between two dictionaries.

        Args:
            old: The old dictionary of packages.
            new: The new dictionary of packages.

        Returns:
            A `Change` named tuple containing the added and removed packages.
        """
        old_keys = set(old.keys())
        new_keys = set(new.keys())
        added = new_keys - old_keys
        removed = old_keys - new_keys
        return Change(added=added, removed=removed)

    dependencies_change = get_changes(
        old_package_json_content.get("dependencies", {}),
        new_package_json_content.get("dependencies", {}),
    )
    dev_dependencies_change = get_changes(
        old_package_json_content.get("devDependencies", {}),
        new_package_json_content.get("devDependencies", {}),
    )

    return dependencies_change, dev_dependencies_change


def kill(proc_pid: int):
    """Kills a process and all its child processes.

    Requires the `psutil` library to be installed.

    Args:
        proc_pid: The process ID of the process to be killed.

    Example:
        >>> kill(1234)
    """
    import psutil

    process = psutil.Process(proc_pid)
    for proc in process.children(recursive=True):
        proc.kill()
    process.kill()


def notify_frontend(url: str, backend_present: bool):
    """Output a string notifying where the frontend is running.

    Args:
        url: The URL where the frontend is running.
        backend_present: Whether the backend is present.
    """
    console.print(
        f"App running at: [bold green]{url.rstrip('/')}/[/bold green]{' (Frontend-only mode)' if not backend_present else ''}"
    )


def notify_backend():
    """Output a string notifying where the backend is running."""
    console.print(
        f"Backend running at: [bold green]http://0.0.0.0:{get_config().backend_port}[/bold green]"
    )


# run_process_and_launch_url is assumed to be used
# only to launch the frontend
# If this is not the case, might have to change the logic
def run_process_and_launch_url(
    run_command: list[str | None], backend_present: bool = True
):
    """Run the process and launch the URL.

    Args:
        run_command: The command to run.
        backend_present: Whether the backend is present.
    """
    from reflex.utils import processes

    json_file_path = get_web_dir() / constants.PackageJson.PATH
    last_content, last_hash = get_package_json_and_hash(json_file_path)
    process = None
    first_run = True

    while True:
        if process is None:
            kwargs: dict[str, Any] = {
                "env": {
                    **os.environ,
                    "NO_COLOR": "1",
                }
            }
            if constants.IS_WINDOWS and backend_present:
                kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP  # pyright: ignore [reportAttributeAccessIssue]
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
                new_content, new_hash = get_package_json_and_hash(json_file_path)
                if new_hash != last_hash:
                    dependencies_change, dev_dependencies_change = (
                        get_different_packages(last_content, new_content)
                    )
                    last_content, last_hash = new_content, new_hash
                    console.info(
                        "Detected changes in package.json.\n"
                        + format_change("Dependencies", dependencies_change)
                        + format_change("Dev Dependencies", dev_dependencies_change)
                    )

                match = re.search(constants.ReactRouter.FRONTEND_LISTENING_REGEX, line)
                if match:
                    if first_run:
                        url = match.group(1)
                        if get_config().frontend_path != "":
                            url = urljoin(url, get_config().frontend_path)

                        notify_frontend(url, backend_present)
                        if backend_present:
                            notify_backend()
                        first_run = False
                    else:
                        console.print("Frontend is restarting...")

        if process is not None:
            break  # while True


def run_frontend(root: Path, port: str, backend_present: bool = True):
    """Run the frontend.

    Args:
        root: The root path of the project.
        port: The port to run the frontend on.
        backend_present: Whether the backend is present.
    """
    from reflex.utils import js_runtimes

    # validate dependencies before run
    js_runtimes.validate_frontend_dependencies(init=False)

    # Run the frontend in development mode.
    console.rule("[bold green]App Running")
    os.environ["PORT"] = str(get_config().frontend_port if port is None else port)
    run_process_and_launch_url(
        [
            *js_runtimes.get_js_package_executor(raise_on_none=True)[0],
            "run",
            "dev",
        ],
        backend_present,
    )


def notify_app_running():
    """Notify that the app is running."""
    console.rule("[bold green]App Running")


def run_frontend_prod(root: Path, port: str, backend_present: bool = True):
    """Run the frontend.

    Args:
        root: The root path of the project (to keep same API as run_frontend).
        port: The port to run the frontend on.
        backend_present: Whether the backend is present.
    """
    from reflex.utils import js_runtimes

    # Set the port.
    os.environ["PORT"] = str(get_config().frontend_port if port is None else port)
    # validate dependencies before run
    js_runtimes.validate_frontend_dependencies(init=False)
    # Run the frontend in production mode.
    notify_app_running()
    run_process_and_launch_url(
        [*js_runtimes.get_js_package_executor(raise_on_none=True)[0], "run", "prod"],
        backend_present,
    )


@once
def _warn_user_about_uvicorn():
    console.warn(
        "Using Uvicorn for backend as it is installed. This behavior will change in 0.8.0 to use Granian by default."
    )


def should_use_granian():
    """Whether to use Granian for backend.

    Returns:
        True if Granian should be used.
    """
    if environment.REFLEX_USE_GRANIAN.is_set():
        return environment.REFLEX_USE_GRANIAN.get()
    if (
        importlib.util.find_spec("uvicorn") is None
        or importlib.util.find_spec("gunicorn") is None
    ):
        return True
    _warn_user_about_uvicorn()
    return False


def get_app_module():
    """Get the app module for the backend.

    Returns:
        The app module for the backend.
    """
    return get_config().module


def get_app_instance():
    """Get the app module for the backend.

    Returns:
        The app module for the backend.
    """
    return f"{get_app_module()}:{constants.CompileVars.APP}"


def get_app_file() -> Path:
    """Get the app file for the backend.

    Returns:
        The app file for the backend.

    Raises:
        ImportError: If the app module is not found.
    """
    current_working_dir = str(Path.cwd())
    if current_working_dir not in sys.path:
        # Add the current working directory to sys.path
        sys.path.insert(0, current_working_dir)
    app_module = get_app_module()
    module_path = get_module_path(app_module)
    if module_path is None:
        msg = f"Module {app_module} not found. Make sure the module is installed."
        raise ImportError(msg)
    return module_path


def get_app_instance_from_file() -> str:
    """Get the app module for the backend.

    Returns:
        The app module for the backend.
    """
    return f"{get_app_file()}:{constants.CompileVars.APP}"


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
        # We import reflex app because this lets granian cache the module
        import reflex.app  # noqa: F401

        run_granian_backend(host, port, loglevel)
    else:
        run_uvicorn_backend(host, port, loglevel)


def _has_child_file(directory: Path, file_name: str) -> bool:
    """Check if a directory has a child file with the given name.

    Args:
        directory: The directory to check.
        file_name: The name of the file to look for.

    Returns:
        True if the directory has a child file with the given name, False otherwise.
    """
    return any(child_file.name == file_name for child_file in directory.iterdir())


def get_reload_paths() -> Sequence[Path]:
    """Get the reload paths for the backend.

    Returns:
        The reload paths for the backend.

    Raises:
        RuntimeError: If the `__init__.py` file is found in the app root directory.
    """
    config = get_config()
    reload_paths = [Path.cwd()]
    app_module = config.module
    module_path = get_module_path(app_module)
    if module_path is not None:
        module_path = module_path.parent

        while module_path.parent.name and _has_child_file(module_path, "__init__.py"):
            if (
                _has_child_file(module_path, "rxconfig.py")
                and module_path == Path.cwd()
            ):
                init_file = module_path / "__init__.py"
                init_file_content = init_file.read_text()
                if init_file_content.strip():
                    msg = "There should not be an `__init__.py` file in your app root directory"
                    raise RuntimeError(msg)
                console.warn(
                    "Removing `__init__.py` file in the app root directory. "
                    "This file can cause issues with module imports. "
                )
                init_file.unlink()
                break

            # go up a level to find dir without `__init__.py` or with `rxconfig.py`
            module_path = module_path.parent

        reload_paths = [module_path]

    include_dirs = tuple(
        map(Path.absolute, environment.REFLEX_HOT_RELOAD_INCLUDE_PATHS.get())
    )
    exclude_dirs = tuple(
        map(Path.absolute, environment.REFLEX_HOT_RELOAD_EXCLUDE_PATHS.get())
    )

    def is_excluded_by_default(path: Path) -> bool:
        if path.is_dir():
            if path.name.startswith("."):
                # exclude hidden directories
                return True
            if path.name.startswith("__"):
                # ignore things like __pycache__
                return True
        return path.name in (".gitignore", "uploaded_files")

    reload_paths = (
        tuple(
            path.absolute()
            for dir in reload_paths
            for path in dir.iterdir()
            if not is_excluded_by_default(path)
        )
        + include_dirs
    )

    if exclude_dirs:
        reload_paths = tuple(
            path
            for path in reload_paths
            if all(not path.samefile(exclude) for exclude in exclude_dirs)
        )

    console.debug(f"Reload paths: {list(map(str, reload_paths))}")

    return reload_paths


def run_uvicorn_backend(host: str, port: int, loglevel: LogLevel):
    """Run the backend in development mode using Uvicorn.

    Args:
        host: The app host
        port: The app port
        loglevel: The log level.
    """
    import uvicorn

    uvicorn.run(
        app=f"{get_app_instance()}",
        factory=True,
        host=host,
        port=port,
        log_level=loglevel.value,
        reload=True,
        reload_dirs=list(map(str, get_reload_paths())),
        reload_delay=0.1,
    )


HOTRELOAD_IGNORE_EXTENSIONS = (
    "txt",
    "toml",
    "sqlite",
    "yaml",
    "yml",
    "json",
    "sh",
    "bash",
    "log",
    "db",
)

HOTRELOAD_IGNORE_PATTERNS = (
    *[rf"^.*\.{ext}$" for ext in HOTRELOAD_IGNORE_EXTENSIONS],
    r"^[^\.]*$",  # Ignore files without an extension
)


def run_granian_backend(host: str, port: int, loglevel: LogLevel):
    """Run the backend in development mode using Granian.

    Args:
        host: The app host
        port: The app port
        loglevel: The log level.
    """
    console.debug("Using Granian for backend")

    if environment.REFLEX_STRICT_HOT_RELOAD.get():
        import multiprocessing

        multiprocessing.set_start_method("spawn", force=True)

    from granian.constants import Interfaces
    from granian.log import LogLevels
    from granian.server import Server as Granian

    from reflex.environment import _load_dotenv_from_env

    granian_app = Granian(
        target=get_app_instance_from_file(),
        factory=True,
        address=host,
        port=port,
        interface=Interfaces.ASGI,
        log_level=LogLevels(loglevel.value),
        reload=True,
        reload_paths=get_reload_paths(),
        reload_ignore_worker_failure=True,
        reload_ignore_patterns=HOTRELOAD_IGNORE_PATTERNS,
        reload_tick=100,
        workers_kill_timeout=2,
    )

    granian_app.on_reload(_load_dotenv_from_env)

    granian_app.serve()


def run_backend_prod(
    host: str,
    port: int,
    loglevel: constants.LogLevel = constants.LogLevel.ERROR,
    frontend_present: bool = False,
    mount_frontend_compiled_app: bool = False,
):
    """Run the backend.

    Args:
        host: The app host
        port: The app port
        loglevel: The log level.
        frontend_present: Whether the frontend is present.
        mount_frontend_compiled_app: Whether to mount the compiled frontend app with the backend.
    """
    if not frontend_present:
        notify_backend()

    environment.REFLEX_MOUNT_FRONTEND_COMPILED_APP.set(mount_frontend_compiled_app)

    if should_use_granian():
        run_granian_backend_prod(host, port, loglevel)
    else:
        run_uvicorn_backend_prod(host, port, loglevel)


def _get_backend_workers():
    from reflex.utils import processes

    return processes.get_num_workers()


def run_uvicorn_backend_prod(host: str, port: int, loglevel: LogLevel):
    """Run the backend in production mode using Uvicorn.

    Args:
        host: The app host
        port: The app port
        loglevel: The log level.
    """
    import os
    import shlex

    from reflex.utils import processes

    app_module = get_app_instance()

    if constants.IS_WINDOWS:
        command = [
            "uvicorn",
            *("--host", host),
            *("--port", str(port)),
            *("--workers", str(_get_backend_workers())),
            "--factory",
            app_module,
        ]
    else:
        # Parse GUNICORN_CMD_ARGS for user overrides
        env_args = []
        if gunicorn_cmd_args := os.environ.get("GUNICORN_CMD_ARGS", ""):
            env_args = shlex.split(gunicorn_cmd_args)

        # Our default args, then env args (env args win on conflicts)
        command = [
            "gunicorn",
            "--preload",
            *("--worker-class", "uvicorn.workers.UvicornH11Worker"),
            *("--threads", str(_get_backend_workers())),
            *("--bind", f"{host}:{port}"),
            *env_args,
            f"{app_module}()",
        ]

    command += [
        *("--log-level", loglevel.value),
    ]

    processes.new_process(
        command,
        run=True,
        show_logs=True,
        env={
            environment.REFLEX_SKIP_COMPILE.name: "true"
        },  # skip compile for prod backend
    )


def run_granian_backend_prod(host: str, port: int, loglevel: LogLevel):
    """Run the backend in production mode using Granian.

    Args:
        host: The app host
        port: The app port
        loglevel: The log level.
    """
    from granian.constants import Interfaces

    from reflex.utils import processes

    command = [
        "granian",
        *("--log-level", "critical"),
        *("--host", host),
        *("--port", str(port)),
        *("--interface", str(Interfaces.ASGI)),
        *("--factory", get_app_instance_from_file()),
    ]

    extra_env = {
        environment.REFLEX_SKIP_COMPILE.name: "true",  # skip compile for prod backend
    }

    if "GRANIAN_WORKERS" not in os.environ:
        extra_env["GRANIAN_WORKERS"] = str(_get_backend_workers())

    processes.new_process(
        command,
        run=True,
        show_logs=True,
        env=extra_env,
    )


def output_system_info():
    """Show system information if the loglevel is in DEBUG."""
    if console._LOG_LEVEL > constants.LogLevel.DEBUG:
        return

    from reflex.utils import js_runtimes

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
        f"[Node {js_runtimes.get_node_version()} (Minimum: {constants.Node.MIN_VERSION}) (PATH:{path_ops.get_node_path()})]",
    ]

    system = platform.system()

    dependencies.append(
        f"[Bun {js_runtimes.get_bun_version()} (Minimum: {constants.Bun.MIN_VERSION}) (PATH: {path_ops.get_bun_path()})]"
    )

    if system == "Linux":
        os_version = platform.freedesktop_os_release().get("PRETTY_NAME", "Unknown")
    else:
        os_version = platform.version()

    dependencies.append(f"[OS {platform.system()} {os_version}]")

    for dep in dependencies:
        console.debug(f"{dep}")

    console.debug(
        f"Using package installer at: {js_runtimes.get_nodejs_compatible_package_managers(raise_on_none=False)}"
    )
    console.debug(
        f"Using package executer at: {js_runtimes.get_js_package_executor(raise_on_none=False)}"
    )
    if system != "Windows":
        console.debug(f"Unzip path: {path_ops.which('unzip')}")


def is_testing_env() -> bool:
    """Whether the app is running in a testing environment.

    Returns:
        True if the app is running in under pytest.
    """
    return constants.PYTEST_CURRENT_TEST in os.environ


def is_in_app_harness() -> bool:
    """Whether the app is running in the app harness.

    Returns:
        True if the app is running in the app harness.
    """
    return constants.APP_HARNESS_FLAG in os.environ


def is_prod_mode() -> bool:
    """Check if the app is running in production mode.

    Returns:
        True if the app is running in production mode or False if running in dev mode.
    """
    current_mode = environment.REFLEX_ENV_MODE.get()
    return current_mode == constants.Env.PROD


def should_prerender_routes() -> bool:
    """Check if the app should prerender routes.

    Returns:
        True if the app should prerender routes.
    """
    if not environment.REFLEX_SSR.is_set():
        return is_prod_mode()
    return environment.REFLEX_SSR.get()


def get_compile_context() -> constants.CompileContext:
    """Check if the app is compiled for deploy.

    Returns:
        Whether the app is being compiled for deploy.
    """
    return environment.REFLEX_COMPILE_CONTEXT.get()
