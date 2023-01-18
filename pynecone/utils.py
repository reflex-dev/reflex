"""General utility functions."""

from __future__ import annotations

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
from typing import _GenericAlias  # type: ignore
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
)
from urllib.parse import urlparse

import plotly.graph_objects as go
import typer
import uvicorn
from plotly.io import to_json
from redis import Redis
from rich.console import Console

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

    try:
        from typing import _SpecialGenericAlias  # type: ignore

        if isinstance(cls, _SpecialGenericAlias):
            return True
    except ImportError:
        pass

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
    try:
        from typing import _UnionGenericAlias  # type: ignore

        return isinstance(cls, _UnionGenericAlias)
    except ImportError:
        pass

    if is_generic_alias(cls):
        return cls.__origin__ == Union

    return False


def get_base_class(cls: GenericType) -> Type:
    """Get the base class of a class.

    Args:
        cls: The class.

    Returns:
        The base class of the class.
    """
    if is_union(cls):
        return tuple(get_base_class(arg) for arg in get_args(cls))

    if is_generic_alias(cls):
        return get_base_class(cls.__origin__)

    return cls


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
    if cls == Any or cls == Callable:
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
        return Config(app_name="")


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
    except Exception as e:
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
    app = __import__(module, fromlist=(constants.APP_VAR,))
    return app


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
    """Install bun onto the user's system."""
    # Bun is not supported on Windows.
    if platform.system() == "Windows":
        console.log("Skipping bun installation on Windows.")
        return

    # Only install if bun is not already installed.
    if not os.path.exists(get_package_manager()):
        console.log("Installing bun...")
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
    template_version = open(constants.PCVERSION_TEMPLATE_FILE).read()
    if not os.path.exists(constants.PCVERSION_APP_FILE):
        return False
    app_version = open(constants.PCVERSION_APP_FILE).read()
    return app_version >= template_version


def export_app(app: App, zip: bool = False):
    """Zip up the app for deployment.

    Args:
        app: The app.
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
        cmd = r"cd .web/_static && zip -r ../../frontend.zip ./* && cd ../.. && zip -r backend.zip ./* -x .web/\* ./assets\* ./frontend.zip\* ./backend.zip\*"
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


def run_frontend(app: App, root: Path):
    """Run the frontend.

    Args:
        app: The app.
        root: root path of the project.
    """
    # Set up the frontend.
    setup_frontend(root)

    # Compile the frontend.
    app.compile(force_compile=True)

    # Run the frontend in development mode.
    console.rule("[bold green]App Running")
    os.environ["PORT"] = get_config().port

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


def run_frontend_prod(app: App, root: Path):
    """Run the frontend.

    Args:
        app: The app.
        root: root path of the project.
    """
    # Set up the frontend.
    setup_frontend(root)

    # Export the app.
    export_app(app)

    os.environ["PORT"] = get_config().port

    # Run the frontend in production mode.
    subprocess.Popen(
        [get_package_manager(), "run", "prod"], cwd=constants.WEB_DIR, env=os.environ
    )


def get_num_workers() -> int:
    """Get the number of backend worker processes.

    Returns:
        The number of backend worker processes.
    """
    if get_redis() is None:
        # If there is no redis, then just use 1 worker.
        return 1

    # Use the number of cores * 2 + 1.
    return (os.cpu_count() or 1) * 2 + 1


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


def run_backend(app_name: str, loglevel: constants.LogLevel = constants.LogLevel.ERROR):
    """Run the backend.

    Args:
        app_name: The app name.
        loglevel: The log level.
    """
    uvicorn.run(
        f"{app_name}:{constants.APP_VAR}.{constants.API_VAR}",
        host=constants.BACKEND_HOST,
        port=get_api_port(),
        log_level=loglevel,
        reload=True,
    )


def run_backend_prod(
    app_name: str, loglevel: constants.LogLevel = constants.LogLevel.ERROR
):
    """Run the backend.

    Args:
        app_name: The app name.
        loglevel: The log level.
    """
    num_workers = get_num_workers()
    command = constants.RUN_BACKEND_PROD + [
        "--bind",
        f"0.0.0.0:{get_api_port()}",
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


def verify_path_validity(path: str) -> None:
    """Verify if the path is valid, and throw an error if not.

    Args:
        path: the path that need to be checked

    Raises:
        ValueError: explains what is wrong with the path.
    """
    pattern = catchall_in_route(path)
    if pattern and not path.endswith(pattern):
        raise ValueError(f"Catch-all must be the last part of the URL: {path}")


def get_path_args(path: str) -> Dict[str, str]:
    """Get the path arguments for the given path.

    Args:
        path: The path to get the arguments for.

    Returns:
        The path arguments.
    """

    def add_path_arg(match: re.Match[str], type_: str):
        """Add arg from regex search result.

        Args:
            match: result of a regex search
            type_: the assigned type for this arg

        Raises:
            ValueError: explains what is wrong with the path.
        """
        arg_name = match.groups()[0]
        if arg_name in args:
            raise ValueError(
                f"arg name [{arg_name}] is used more than once in this URL"
            )
        args[arg_name] = type_

    # Regex to check for path args.
    check = constants.RouteRegex.ARG
    check_strict_catchall = constants.RouteRegex.STRICT_CATCHALL
    check_opt_catchall = constants.RouteRegex.OPT_CATCHALL

    # Iterate over the path parts and check for path args.
    args = {}
    for part in path.split("/"):
        match_opt = check_opt_catchall.match(part)
        if match_opt:
            add_path_arg(match_opt, constants.PathArgType.LIST)
            break

        match_strict = check_strict_catchall.match(part)
        if match_strict:
            add_path_arg(match_strict, constants.PathArgType.LIST)
            break

        match = check.match(part)
        if match:
            # Add the path arg to the list.
            add_path_arg(match, constants.PathArgType.SINGLE)
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
    route = route.strip(os.path.sep)
    route = to_snake_case(route).replace("_", "-")
    if route == "":
        return constants.INDEX_ROUTE
    return route


def format_cond(
    cond: str, true_value: str, false_value: str = '""', is_nested: bool = False
) -> str:
    """Format a conditional expression.

    Args:
        cond: The cond.
        true_value: The value to return if the cond is true.
        false_value: The value to return if the cond is false.
        is_nested: Whether the cond is nested.

    Returns:
        The formatted conditional expression.
    """
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
    except:
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
        return json.loads(to_json(value))["data"]

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
    args = inspect.getfullargspec(fn).args
    if len(args) == 0:
        out = fn()
    elif len(args) == 1:
        out = fn(arg)
    else:
        raise ValueError(f"Lambda {fn} must have 0 or 1 arguments.")
    if not isinstance(out, List):
        out = [out]
    return out


def get_handler_args(event_spec: EventSpec, arg: Var) -> Tuple[Tuple[str, str], ...]:
    """Get the handler args for the given event spec.

    Args:
        event_spec: The event spec.
        arg: The controlled event argument.

    Returns:
        The handler args.
    """
    args = inspect.getfullargspec(event_spec.handler.fn).args
    if len(args) > 2:
        return event_spec.args
    else:
        return ((args[1], arg.name),)


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


# Store this here for performance.
StateBases = get_base_class(StateVar)
