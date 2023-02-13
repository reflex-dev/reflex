"""General utility functions."""

from __future__ import annotations

import contextlib
import inspect
import json
import os
import platform
import random
import re
import shutil
import signal
import string
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from subprocess import DEVNULL, PIPE, STDOUT
from types import ModuleType
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Tuple,
    Type,
    Union,
    _GenericAlias,  # type: ignore  # type: ignore
)
from urllib.parse import urlparse

import plotly.graph_objects as go
import psutil
import typer
import uvicorn
from plotly.io import to_json
from redis import Redis
from rich.console import Console
from rich.prompt import Prompt

from pynecone import constants
from pynecone.base import Base

if TYPE_CHECKING:
    from pynecone.app import App
    from pynecone.components.component import ImportDict
    from pynecone.config import Config
    from pynecone.event import Event, EventHandler, EventSpec
    from pynecone.var import Var

# Shorthand for join.
join = os.linesep.join

# Console for pretty printing.
console = Console()

# Union of generic types.
GenericType = Union[Type, _GenericAlias]

# Valid state var types.
PrimitiveType = Union[int, float, bool, str, list, dict, tuple]
StateVar = Union[PrimitiveType, Base, None]


def deprecate(msg: str):
    """Print a deprecation warning.

    Args:
        msg: The deprecation message.
    """
    console.print(f"[yellow]DeprecationWarning: {msg}[/yellow]")


def get_args(alias: _GenericAlias) -> Tuple[Type, ...]:
    """Get the arguments of a type alias.

    Args:
        alias: The type alias.

    Returns:
        The arguments of the type alias.
    """
    return alias.__args__


def is_generic_alias(cls: GenericType) -> bool:
    """Check whether the class is a generic alias.

    Args:
        cls: The class to check.

    Returns:
        Whether the class is a generic alias.
    """
    # For older versions of Python.
    if isinstance(cls, _GenericAlias):
        return True

    with contextlib.suppress(ImportError):
        from typing import _SpecialGenericAlias  # type: ignore

        if isinstance(cls, _SpecialGenericAlias):
            return True
    # For newer versions of Python.
    try:
        from types import GenericAlias  # type: ignore

        return isinstance(cls, GenericAlias)
    except ImportError:
        return False


def is_union(cls: GenericType) -> bool:
    """Check if a class is a Union.

    Args:
        cls: The class to check.

    Returns:
        Whether the class is a Union.
    """
    with contextlib.suppress(ImportError):
        from typing import _UnionGenericAlias  # type: ignore

        return isinstance(cls, _UnionGenericAlias)
    return cls.__origin__ == Union if is_generic_alias(cls) else False


def get_base_class(cls: GenericType) -> Type:
    """Get the base class of a class.

    Args:
        cls: The class.

    Returns:
        The base class of the class.
    """
    if is_union(cls):
        return tuple(get_base_class(arg) for arg in get_args(cls))

    return get_base_class(cls.__origin__) if is_generic_alias(cls) else cls


def _issubclass(cls: GenericType, cls_check: GenericType) -> bool:
    """Check if a class is a subclass of another class.

    Args:
        cls: The class to check.
        cls_check: The class to check against.

    Returns:
        Whether the class is a subclass of the other class.
    """
    # Special check for Any.
    if cls_check == Any:
        return True
    if cls in [Any, Callable]:
        return False
    cls_base = get_base_class(cls)
    cls_check_base = get_base_class(cls_check)
    return cls_check_base == Any or issubclass(cls_base, cls_check_base)


def _isinstance(obj: Any, cls: GenericType) -> bool:
    """Check if an object is an instance of a class.

    Args:
        obj: The object to check.
        cls: The class to check against.

    Returns:
        Whether the object is an instance of the class.
    """
    return isinstance(obj, get_base_class(cls))


def rm(path: str):
    """Remove a file or directory.

    Args:
        path: The path to the file or directory.
    """
    if os.path.isdir(path):
        shutil.rmtree(path)
    elif os.path.isfile(path):
        os.remove(path)


def cp(src: str, dest: str, overwrite: bool = True) -> bool:
    """Copy a file or directory.

    Args:
        src: The path to the file or directory.
        dest: The path to the destination.
        overwrite: Whether to overwrite the destination.

    Returns:
        Whether the copy was successful.
    """
    if src == dest:
        return False
    if not overwrite and os.path.exists(dest):
        return False
    if os.path.isdir(src):
        rm(dest)
        shutil.copytree(src, dest)
    else:
        shutil.copyfile(src, dest)
    return True


def mv(src: str, dest: str, overwrite: bool = True) -> bool:
    """Move a file or directory.

    Args:
        src: The path to the file or directory.
        dest: The path to the destination.
        overwrite: Whether to overwrite the destination.

    Returns:
        Whether the move was successful.
    """
    if src == dest:
        return False
    if not overwrite and os.path.exists(dest):
        return False
    rm(dest)
    shutil.move(src, dest)
    return True


def mkdir(path: str):
    """Create a directory.

    Args:
        path: The path to the directory.
    """
    if not os.path.exists(path):
        os.makedirs(path)


def ln(src: str, dest: str, overwrite: bool = False) -> bool:
    """Create a symbolic link.

    Args:
        src: The path to the file or directory.
        dest: The path to the destination.
        overwrite: Whether to overwrite the destination.

    Returns:
        Whether the link was successful.
    """
    if src == dest:
        return False
    if not overwrite and (os.path.exists(dest) or os.path.islink(dest)):
        return False
    if os.path.isdir(src):
        rm(dest)
        os.symlink(src, dest, target_is_directory=True)
    else:
        os.symlink(src, dest)
    return True


def kill(pid):
    """Kill a process.

    Args:
        pid: The process ID.
    """
    os.kill(pid, signal.SIGTERM)


def which(program: str) -> Optional[str]:
    """Find the path to an executable.

    Args:
        program: The name of the executable.

    Returns:
        The path to the executable.
    """
    return shutil.which(program)


def get_config() -> Config:
    """Get the app config.

    Returns:
        The app config.
    """
    from pynecone.config import Config

    sys.path.append(os.getcwd())
    try:
        return __import__(constants.CONFIG_MODULE).config
    except ImportError:
        return Config(app_name="")  # type: ignore


def check_node_version(min_version):
    """Check the version of Node.js.

    Args:
        min_version: The minimum version of Node.js required.

    Returns:
        Whether the version of Node.js is high enough.
    """
    try:
        # Run the node -v command and capture the output
        result = subprocess.run(
            ["node", "-v"], stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        # The output will be in the form "vX.Y.Z", so we can split it on the "v" character and take the second part
        version = result.stdout.decode().strip().split("v")[1]
        # Compare the version numbers
        return version.split(".") >= min_version.split(".")
    except Exception:
        return False


def get_package_manager() -> str:
    """Get the package manager executable.

    Returns:
        The path to the package manager.

    Raises:
        FileNotFoundError: If bun or npm is not installed.
        Exit: If the app directory is invalid.

    """
    # Check that the node version is valid.
    if not check_node_version(constants.MIN_NODE_VERSION):
        console.print(
            f"[red]Node.js version {constants.MIN_NODE_VERSION} or higher is required to run Pynecone."
        )
        raise typer.Exit()

    # On Windows, we use npm instead of bun.
    if platform.system() == "Windows":
        npm_path = which("npm")
        if npm_path is None:
            raise FileNotFoundError("Pynecone requires npm to be installed on Windows.")
        return npm_path

    # On other platforms, we use bun.
    return os.path.expandvars(get_config().bun_path)


def get_app() -> ModuleType:
    """Get the app module based on the default config.

    Returns:
        The app based on the default config.
    """
    config = get_config()
    module = ".".join([config.app_name, config.app_name])
    sys.path.insert(0, os.getcwd())
    return __import__(module, fromlist=(constants.APP_VAR,))


def create_config(app_name: str):
    """Create a new pcconfig file.

    Args:
        app_name: The name of the app.
    """
    # Import here to avoid circular imports.
    from pynecone.compiler import templates

    with open(constants.CONFIG_FILE, "w") as f:
        f.write(templates.PCCONFIG.format(app_name=app_name))


def initialize_gitignore():
    """Initialize the template .gitignore file."""
    # The files to add to the .gitignore file.
    files = constants.DEFAULT_GITIGNORE

    # Subtract current ignored files.
    if os.path.exists(constants.GITIGNORE_FILE):
        with open(constants.GITIGNORE_FILE, "r") as f:
            files -= set(f.read().splitlines())

    # Add the new files to the .gitignore file.
    with open(constants.GITIGNORE_FILE, "a") as f:
        f.write(join(files))


def initialize_app_directory(app_name: str):
    """Initialize the app directory on pc init.

    Args:
        app_name: The name of the app.
    """
    console.log("Initializing the app directory.")
    cp(constants.APP_TEMPLATE_DIR, app_name)
    mv(
        os.path.join(app_name, constants.APP_TEMPLATE_FILE),
        os.path.join(app_name, app_name + constants.PY_EXT),
    )
    cp(constants.ASSETS_TEMPLATE_DIR, constants.APP_ASSETS_DIR)


def initialize_web_directory():
    """Initialize the web directory on pc init."""
    console.log("Initializing the web directory.")
    rm(os.path.join(constants.WEB_TEMPLATE_DIR, constants.NODE_MODULES))
    rm(os.path.join(constants.WEB_TEMPLATE_DIR, constants.PACKAGE_LOCK))
    cp(constants.WEB_TEMPLATE_DIR, constants.WEB_DIR)


def install_bun():
    """Install bun onto the user's system.

    Raises:
        FileNotFoundError: If the required packages are not installed.
    """
    # Bun is not supported on Windows.
    if platform.system() == "Windows":
        console.log("Skipping bun installation on Windows.")
        return

    # Only install if bun is not already installed.
    if not os.path.exists(get_package_manager()):
        console.log("Installing bun...")

        # Check if curl is installed
        curl_path = which("curl")
        if curl_path is None:
            raise FileNotFoundError("Pynecone requires curl to be installed.")

        # Check if unzip is installed
        unzip_path = which("unzip")
        if unzip_path is None:
            raise FileNotFoundError("Pynecone requires unzip to be installed.")

        os.system(constants.INSTALL_BUN)


def install_frontend_packages():
    """Install the frontend packages."""
    # Install the base packages.
    subprocess.run(
        [get_package_manager(), "install"], cwd=constants.WEB_DIR, stdout=PIPE
    )

    # Install the app packages.
    packages = get_config().frontend_packages
    if len(packages) > 0:
        subprocess.run(
            [get_package_manager(), "add", *packages],
            cwd=constants.WEB_DIR,
            stdout=PIPE,
        )


def is_initialized() -> bool:
    """Check whether the app is initialized.

    Returns:
        Whether the app is initialized in the current directory.
    """
    return os.path.exists(constants.CONFIG_FILE) and os.path.exists(constants.WEB_DIR)


def is_latest_template() -> bool:
    """Whether the app is using the latest template.

    Returns:
        Whether the app is using the latest template.
    """
    with open(constants.PCVERSION_TEMPLATE_FILE) as f:  # type: ignore
        template_version = f.read()
    if not os.path.exists(constants.PCVERSION_APP_FILE):
        return False
    with open(constants.PCVERSION_APP_FILE) as f:  # type: ignore
        app_version = f.read()
    return app_version >= template_version


def export_app(
    app: App, backend: bool = True, frontend: bool = True, zip: bool = False
):
    """Zip up the app for deployment.

    Args:
        app: The app.
        backend: Whether to zip up the backend app.
        frontend: Whether to zip up the frontend app.
        zip: Whether to zip the app.
    """
    # Force compile the app.
    app.compile(force_compile=True)

    # Remove the static folder.
    rm(constants.WEB_STATIC_DIR)

    # Export the Next app.
    subprocess.run([get_package_manager(), "run", "export"], cwd=constants.WEB_DIR)

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
        cmd = r'''powershell -Command "Get-ChildItem .\* -Directory  | where {`$_.Name -notin @('.web', 'assets', 'frontend.zip', 'backend.zip')} | Compress-Archive -DestinationPath backend.zip -Update"'''
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


def setup_frontend(root: Path):
    """Set up the frontend.

    Args:
        root: root path of the project.
    """
    # Initialize the web directory if it doesn't exist.
    cp(constants.WEB_TEMPLATE_DIR, str(root / constants.WEB_DIR), overwrite=False)

    # Install the frontend packages.
    console.rule("[bold]Installing frontend packages")
    install_frontend_packages()

    # copy asset files to public folder
    mkdir(str(root / constants.WEB_ASSETS_DIR))
    cp(
        src=str(root / constants.APP_ASSETS_DIR),
        dest=str(root / constants.WEB_ASSETS_DIR),
    )


def run_frontend(app: App, root: Path, port: str):
    """Run the frontend.

    Args:
        app: The app.
        root: root path of the project.
        port: port of the app.
    """
    # Set up the frontend.
    setup_frontend(root)

    # Compile the frontend.
    app.compile(force_compile=True)

    # Run the frontend in development mode.
    console.rule("[bold green]App Running")
    os.environ["PORT"] = get_config().port if port is None else port

    subprocess.Popen(
        [get_package_manager(), "run", "next", "telemetry", "disable"],
        cwd=constants.WEB_DIR,
        env=os.environ,
        stdout=DEVNULL,
        stderr=STDOUT,
    )

    subprocess.Popen(
        [get_package_manager(), "run", "dev"], cwd=constants.WEB_DIR, env=os.environ
    )


def run_frontend_prod(app: App, root: Path, port: str):
    """Run the frontend.

    Args:
        app: The app.
        root: root path of the project.
        port: port of the app.
    """
    # Set up the frontend.
    setup_frontend(root)

    # Export the app.
    export_app(app)

    os.environ["PORT"] = get_config().port if port is None else port

    # Run the frontend in production mode.
    subprocess.Popen(
        [get_package_manager(), "run", "prod"], cwd=constants.WEB_DIR, env=os.environ
    )


def get_num_workers() -> int:
    """Get the number of backend worker processes.

    Returns:
        The number of backend worker processes.
    """
    return 1 if get_redis() is None else (os.cpu_count() or 1) * 2 + 1


def get_api_port() -> int:
    """Get the API port.

    Returns:
        The API port.
    """
    port = urlparse(get_config().api_url).port
    if port is None:
        port = urlparse(constants.API_URL).port
    assert port is not None
    return port


def get_process_on_port(port) -> Optional[psutil.Process]:
    """Get the process on the given port.

    Args:
        port: The port.

    Returns:
        The process on the given port.
    """
    for proc in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            for conns in proc.connections(kind="inet"):
                if conns.laddr.port == int(port):
                    return proc
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    return None


def is_process_on_port(port) -> bool:
    """Check if a process is running on the given port.

    Args:
        port: The port.

    Returns:
        Whether a process is running on the given port.
    """
    return get_process_on_port(port) is not None


def kill_process_on_port(port):
    """Kill the process on the given port.

    Args:
        port: The port.
    """
    if get_process_on_port(port) is not None:
        get_process_on_port(port).kill()  # type: ignore


def change_or_terminate_port(port, _type) -> str:
    """Terminate or change the port.

    Args:
        port: The port.
        _type: The type of the port.

    Returns:
        The new port or the current one.
    """
    console.print(
        f"Something is already running on port [bold underline]{port}[/bold underline]. This is the port the {_type} runs on."
    )
    frontend_action = Prompt.ask("Kill or change it?", choices=["k", "c", "n"])
    if frontend_action == "k":
        kill_process_on_port(port)
        return port
    elif frontend_action == "c":
        new_port = Prompt.ask("Specify the new port")

        # Check if also the new port is used
        if is_process_on_port(new_port):
            return change_or_terminate_port(new_port, _type)
        else:
            console.print(
                f"The {_type} will run on port [bold underline]{new_port}[/bold underline]."
            )
            return new_port
    else:
        console.print("Exiting...")
        sys.exit()


def setup_backend():
    """Set up backend.

    Specifically ensures backend database is updated when running --no-frontend.
    """
    # Import here to avoid circular imports.
    from pynecone.model import Model

    config = get_config()
    if config.db_url is not None:
        Model.create_all()


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

    uvicorn.run(
        f"{app_name}:{constants.APP_VAR}.{constants.API_VAR}",
        host=constants.BACKEND_HOST,
        port=port,
        log_level=loglevel,
        reload=True,
    )


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

    num_workers = get_num_workers()
    command = constants.RUN_BACKEND_PROD + [
        "--bind",
        f"0.0.0.0:{port}",
        "--workers",
        str(num_workers),
        "--threads",
        str(num_workers),
        "--log-level",
        str(loglevel),
        f"{app_name}:{constants.APP_VAR}()",
    ]
    subprocess.run(command)


def get_production_backend_url() -> str:
    """Get the production backend URL.

    Returns:
        The production backend URL.
    """
    config = get_config()
    return constants.PRODUCTION_BACKEND_URL.format(
        username=config.username,
        app_name=config.app_name,
    )


def to_snake_case(text: str) -> str:
    """Convert a string to snake case.

    The words in the text are converted to lowercase and
    separated by underscores.

    Args:
        text: The string to convert.

    Returns:
        The snake case string.
    """
    s1 = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", text)
    return re.sub("([a-z0-9])([A-Z])", r"\1_\2", s1).lower()


def to_camel_case(text: str) -> str:
    """Convert a string to camel case.

    The first word in the text is converted to lowercase and
    the rest of the words are converted to title case, removing underscores.

    Args:
        text: The string to convert.

    Returns:
        The camel case string.
    """
    if "_" not in text:
        return text
    camel = "".join(
        word.capitalize() if i > 0 else word.lower()
        for i, word in enumerate(text.lstrip("_").split("_"))
    )
    prefix = "_" if text.startswith("_") else ""
    return prefix + camel


def to_title_case(text: str) -> str:
    """Convert a string from snake case to title case.

    Args:
        text: The string to convert.

    Returns:
        The title case string.
    """
    return "".join(word.capitalize() for word in text.split("_"))


WRAP_MAP = {
    "{": "}",
    "(": ")",
    "[": "]",
    "<": ">",
    '"': '"',
    "'": "'",
    "`": "`",
}


def get_close_char(open: str, close: Optional[str] = None) -> str:
    """Check if the given character is a valid brace.

    Args:
        open: The open character.
        close: The close character if provided.

    Returns:
        The close character.

    Raises:
        ValueError: If the open character is not a valid brace.
    """
    if close is not None:
        return close
    if open not in WRAP_MAP:
        raise ValueError(f"Invalid wrap open: {open}, must be one of {WRAP_MAP.keys()}")
    return WRAP_MAP[open]


def is_wrapped(text: str, open: str, close: Optional[str] = None) -> bool:
    """Check if the given text is wrapped in the given open and close characters.

    Args:
        text: The text to check.
        open: The open character.
        close: The close character.

    Returns:
        Whether the text is wrapped.
    """
    close = get_close_char(open, close)
    return text.startswith(open) and text.endswith(close)


def wrap(
    text: str,
    open: str,
    close: Optional[str] = None,
    check_first: bool = True,
    num: int = 1,
) -> str:
    """Wrap the given text in the given open and close characters.

    Args:
        text: The text to wrap.
        open: The open character.
        close: The close character.
        check_first: Whether to check if the text is already wrapped.
        num: The number of times to wrap the text.

    Returns:
        The wrapped text.
    """
    close = get_close_char(open, close)

    # If desired, check if the text is already wrapped in braces.
    if check_first and is_wrapped(text=text, open=open, close=close):
        return text

    # Wrap the text in braces.
    return f"{open * num}{text}{close * num}"


def indent(text: str, indent_level: int = 2) -> str:
    """Indent the given text by the given indent level.

    Args:
        text: The text to indent.
        indent_level: The indent level.

    Returns:
        The indented text.
    """
    lines = text.splitlines()
    if len(lines) < 2:
        return text
    return os.linesep.join(f"{' ' * indent_level}{line}" for line in lines) + os.linesep


def verify_route_validity(route: str) -> None:
    """Verify if the route is valid, and throw an error if not.

    Args:
        route: The route that need to be checked

    Raises:
        ValueError: If the route is invalid.
    """
    pattern = catchall_in_route(route)
    if pattern and not route.endswith(pattern):
        raise ValueError(f"Catch-all must be the last part of the URL: {route}")


def get_route_args(route: str) -> Dict[str, str]:
    """Get the dynamic arguments for the given route.

    Args:
        route: The route to get the arguments for.

    Returns:
        The route arguments.
    """
    args = {}

    def add_route_arg(match: re.Match[str], type_: str):
        """Add arg from regex search result.

        Args:
            match: Result of a regex search
            type_: The assigned type for this arg

        Raises:
            ValueError: If the route is invalid.
        """
        arg_name = match.groups()[0]
        if arg_name in args:
            raise ValueError(
                f"Arg name [{arg_name}] is used more than once in this URL"
            )
        args[arg_name] = type_

    # Regex to check for route args.
    check = constants.RouteRegex.ARG
    check_strict_catchall = constants.RouteRegex.STRICT_CATCHALL
    check_opt_catchall = constants.RouteRegex.OPT_CATCHALL

    # Iterate over the route parts and check for route args.
    for part in route.split("/"):
        match_opt = check_opt_catchall.match(part)
        if match_opt:
            add_route_arg(match_opt, constants.RouteArgType.LIST)
            break

        match_strict = check_strict_catchall.match(part)
        if match_strict:
            add_route_arg(match_strict, constants.RouteArgType.LIST)
            break

        match = check.match(part)
        if match:
            # Add the route arg to the list.
            add_route_arg(match, constants.RouteArgType.SINGLE)
    return args


def catchall_in_route(route: str) -> str:
    """Extract the catchall part from a route.

    Args:
        route: the route from which to extract

    Returns:
        str: the catchall part of the URI
    """
    match_ = constants.RouteRegex.CATCHALL.search(route)
    return match_.group() if match_ else ""


def catchall_prefix(route: str) -> str:
    """Extract the prefix part from a route that contains a catchall.

    Args:
        route: the route from which to extract

    Returns:
        str: the prefix part of the URI
    """
    pattern = catchall_in_route(route)
    return route.replace(pattern, "") if pattern else ""


def format_route(route: str) -> str:
    """Format the given route.

    Args:
        route: The route to format.

    Returns:
        The formatted route.
    """
    # Strip the route.
    route = route.strip("/")
    route = to_snake_case(route).replace("_", "-")

    # If the route is empty, return the index route.
    if route == "":
        return constants.INDEX_ROUTE

    return route


def format_cond(
    cond: str,
    true_value: str,
    false_value: str = '""',
    is_nested: bool = False,
    is_prop=False,
) -> str:
    """Format a conditional expression.

    Args:
        cond: The cond.
        true_value: The value to return if the cond is true.
        false_value: The value to return if the cond is false.
        is_nested: Whether the cond is nested.
        is_prop: Whether the cond is a prop

    Returns:
        The formatted conditional expression.
    """
    # Import here to avoid circular imports.
    from pynecone.var import Var

    if is_prop:
        prop1 = Var.create(true_value, is_string=type(true_value) == str)
        prop2 = Var.create(false_value, is_string=type(false_value) == str)
        assert prop1 is not None and prop2 is not None, "Invalid prop values"
        expr = f"{cond} ? {prop1} : {prop2}".replace("{", "").replace("}", "")
    else:
        expr = f"{cond} ? {true_value} : {false_value}"

    if not is_nested:
        expr = wrap(expr, "{")
    return expr


def format_event_handler(handler: EventHandler) -> str:
    """Format an event handler.

    Args:
        handler: The event handler to format.

    Returns:
        The formatted function.
    """
    # Get the class that defines the event handler.
    parts = handler.fn.__qualname__.split(".")

    # If there's no enclosing class, just return the function name.
    if len(parts) == 1:
        return parts[-1]

    # Get the state and the function name.
    state_name, name = parts[-2:]

    # Construct the full event handler name.
    try:
        # Try to get the state from the module.
        state = vars(sys.modules[handler.fn.__module__])[state_name]
    except Exception:
        # If the state isn't in the module, just return the function name.
        return handler.fn.__qualname__
    return ".".join([state.get_full_name(), name])


def format_event(event_spec: EventSpec) -> str:
    """Format an event.

    Args:
        event_spec: The event to format.

    Returns:
        The compiled event.
    """
    args = ",".join([":".join((name, val)) for name, val in event_spec.args])
    return f"E(\"{format_event_handler(event_spec.handler)}\", {wrap(args, '{')})"


def format_query_params(router_data: Dict[str, Any]) -> Dict[str, str]:
    """Convert back query params name to python-friendly case.

    Args:
        router_data: the router_data dict containing the query params

    Returns:
        The reformatted query params
    """
    params = router_data[constants.RouteVar.QUERY]
    return {k.replace("-", "_"): v for k, v in params.items()}


USED_VARIABLES = set()


def get_unique_variable_name() -> str:
    """Get a unique variable name.

    Returns:
        The unique variable name.
    """
    name = "".join([random.choice(string.ascii_lowercase) for _ in range(8)])
    if name not in USED_VARIABLES:
        USED_VARIABLES.add(name)
        return name
    return get_unique_variable_name()


def get_default_app_name() -> str:
    """Get the default app name.

    The default app name is the name of the current directory.

    Returns:
        The default app name.
    """
    return os.getcwd().split(os.path.sep)[-1].replace("-", "_")


def is_dataframe(value: Type) -> bool:
    """Check if the given value is a dataframe.

    Args:
        value: The value to check.

    Returns:
        Whether the value is a dataframe.
    """
    return value.__name__ == "DataFrame"


def is_figure(value: Type) -> bool:
    """Check if the given value is a figure.

    Args:
        value: The value to check.

    Returns:
        Whether the value is a figure.
    """
    return value.__name__ == "Figure"


def is_valid_var_type(var: Type) -> bool:
    """Check if the given value is a valid prop type.

    Args:
        var: The value to check.

    Returns:
        Whether the value is a valid prop type.
    """
    return _issubclass(var, StateVar) or is_dataframe(var) or is_figure(var)


def format_state(value: Any) -> Dict:
    """Recursively format values in the given state.

    Args:
        value: The state to format.

    Returns:
        The formatted state.

    Raises:
        TypeError: If the given value is not a valid state.
    """
    # Handle dicts.
    if isinstance(value, dict):
        return {k: format_state(v) for k, v in value.items()}

    # Return state vars as is.
    if isinstance(value, StateBases):
        return value

    # Convert plotly figures to JSON.
    if isinstance(value, go.Figure):
        return json.loads(to_json(value))["data"]  # type: ignore

    # Convert pandas dataframes to JSON.
    if is_dataframe(type(value)):
        return {
            "columns": value.columns.tolist(),
            "data": value.values.tolist(),
        }

    raise TypeError(
        "State vars must be primitive Python types, "
        "or subclasses of pc.Base. "
        f"Got var of type {type(value)}."
    )


def get_event(state, event):
    """Get the event from the given state.

    Args:
        state: The state.
        event: The event.

    Returns:
        The event.
    """
    return f"{state.get_name()}.{event}"


def format_string(string: str) -> str:
    """Format the given string as a JS string literal..

    Args:
        string: The string to format.

    Returns:
        The formatted string.
    """
    # Escape backticks.
    string = string.replace(r"\`", "`")
    string = string.replace("`", r"\`")

    # Wrap the string so it looks like {`string`}.
    string = wrap(string, "`")
    string = wrap(string, "{")

    return string


def call_event_handler(event_handler: EventHandler, arg: Var) -> EventSpec:
    """Call an event handler to get the event spec.

    This function will inspect the function signature of the event handler.
    If it takes in an arg, the arg will be passed to the event handler.
    Otherwise, the event handler will be called with no args.

    Args:
        event_handler: The event handler.
        arg: The argument to pass to the event handler.

    Returns:
        The event spec from calling the event handler.
    """
    args = inspect.getfullargspec(event_handler.fn).args
    if len(args) == 1:
        return event_handler()
    assert (
        len(args) == 2
    ), f"Event handler {event_handler.fn} must have 1 or 2 arguments."
    return event_handler(arg)


def call_event_fn(fn: Callable, arg: Var) -> List[EventSpec]:
    """Call a function to a list of event specs.

    The function should return either a single EventSpec or a list of EventSpecs.
    If the function takes in an arg, the arg will be passed to the function.
    Otherwise, the function will be called with no args.

    Args:
        fn: The function to call.
        arg: The argument to pass to the function.

    Returns:
        The event specs from calling the function.

    Raises:
        ValueError: If the lambda has an invalid signature.
    """
    # Import here to avoid circular imports.
    from pynecone.event import EventHandler, EventSpec

    # Get the args of the lambda.
    args = inspect.getfullargspec(fn).args

    # Call the lambda.
    if len(args) == 0:
        out = fn()
    elif len(args) == 1:
        out = fn(arg)
    else:
        raise ValueError(f"Lambda {fn} must have 0 or 1 arguments.")

    # Convert the output to a list.
    if not isinstance(out, List):
        out = [out]

    # Convert any event specs to event specs.
    events = []
    for e in out:
        # Convert handlers to event specs.
        if isinstance(e, EventHandler):
            if len(args) == 0:
                e = e()
            elif len(args) == 1:
                e = e(arg)

        # Make sure the event spec is valid.
        if not isinstance(e, EventSpec):
            raise ValueError(f"Lambda {fn} returned an invalid event spec: {e}.")

        # Add the event spec to the chain.
        events.append(e)

    # Return the events.
    return events


def get_handler_args(event_spec: EventSpec, arg: Var) -> Tuple[Tuple[str, str], ...]:
    """Get the handler args for the given event spec.

    Args:
        event_spec: The event spec.
        arg: The controlled event argument.

    Returns:
        The handler args.

    Raises:
        ValueError: If the event handler has an invalid signature.
    """
    args = inspect.getfullargspec(event_spec.handler.fn).args
    if len(args) < 2:
        raise ValueError(
            f"Event handler has an invalid signature, needed a method with a parameter, got {event_spec.handler}."
        )
    return event_spec.args if len(args) > 2 else ((args[1], arg.name),)


def fix_events(events: Optional[List[Event]], token: str) -> List[Event]:
    """Fix a list of events returned by an event handler.

    Args:
        events: The events to fix.
        token: The user token.

    Returns:
        The fixed events.
    """
    from pynecone.event import Event, EventHandler, EventSpec

    # If the event handler returns nothing, return an empty list.
    if events is None:
        return []

    # If the handler returns a single event, wrap it in a list.
    if not isinstance(events, List):
        events = [events]

    # Fix the events created by the handler.
    out = []
    for e in events:
        # If it is already an event, don't modify it.
        if isinstance(e, Event):
            name = e.name
            payload = e.payload

        # Otherwise, create an event from the event spec.
        else:
            if isinstance(e, EventHandler):
                e = e()
            assert isinstance(e, EventSpec), f"Unexpected event type, {type(e)}."
            name = format_event_handler(e.handler)
            payload = dict(e.args)

        # Create an event and append it to the list.
        out.append(
            Event(
                token=token,
                name=name,
                payload=payload,
            )
        )

    return out


def merge_imports(*imports) -> ImportDict:
    """Merge two import dicts together.

    Args:
        *imports: The list of import dicts to merge.

    Returns:
        The merged import dicts.
    """
    all_imports = defaultdict(set)
    for import_dict in imports:
        for lib, fields in import_dict.items():
            for field in fields:
                all_imports[lib].add(field)
    return all_imports


def get_hydrate_event(state) -> str:
    """Get the name of the hydrate event for the state.

    Args:
        state: The state.

    Returns:
        The name of the hydrate event.
    """
    return get_event(state, constants.HYDRATE)


def get_redis() -> Optional[Redis]:
    """Get the redis client.

    Returns:
        The redis client.
    """
    config = get_config()
    if config.redis_url is None:
        return None
    redis_url, redis_port = config.redis_url.split(":")
    print("Using redis at", config.redis_url)
    return Redis(host=redis_url, port=int(redis_port), db=0)


def is_backend_variable(name: str) -> bool:
    """Check if this variable name correspond to a backend variable.

    Args:
        name: The name of the variable to check

    Returns:
        bool: The result of the check
    """
    return name.startswith("_") and not name.startswith("__")


# Store this here for performance.
StateBases = get_base_class(StateVar)
