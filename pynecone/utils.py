"""General utility functions."""

from __future__ import annotations

import inspect
import json
import os
import random
import re
import shutil
import signal
import string
import subprocess
import sys
from collections import defaultdict
from subprocess import PIPE
from typing import _GenericAlias  # type: ignore
from typing import _UnionGenericAlias  # type: ignore
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

import plotly.graph_objects as go
from plotly.io import to_json
from rich.console import Console

from pynecone import constants

if TYPE_CHECKING:
    from pynecone.components.component import ImportDict
    from pynecone.event import EventHandler, EventSpec
    from pynecone.var import Var


# Shorthand for join.
join = os.linesep.join

# Console for pretty printing.
console = Console()


def get_args(alias: _GenericAlias) -> Tuple[Type, ...]:
    """Get the arguments of a type alias.

    Args:
        alias: The type alias.

    Returns:
        The arguments of the type alias.
    """
    return alias.__args__


def get_base_class(cls: Type) -> Type:
    """Get the base class of a class.

    Args:
        cls: The class.

    Returns:
        The base class of the class.
    """
    # For newer versions of Python.
    try:
        from types import GenericAlias

        if isinstance(cls, GenericAlias):
            return get_base_class(cls.__origin__)
    except:
        pass

    # Check Union types first.
    if isinstance(cls, _UnionGenericAlias):
        return tuple(get_base_class(arg) for arg in get_args(cls))

    # Check other generic aliases.
    if isinstance(cls, _GenericAlias):
        return get_base_class(cls.__origin__)

    # This is the base class.
    return cls


def _issubclass(
    cls: Union[Type, _GenericAlias], cls_check: Union[Type, _GenericAlias]
) -> bool:
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
    if cls == Any:
        return False
    cls_base = get_base_class(cls)
    cls_check_base = get_base_class(cls_check)
    return cls_check_base == Any or issubclass(cls_base, cls_check_base)


def _isinstance(obj: Any, cls: Union[Type, _GenericAlias]) -> bool:
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


def get_config() -> Any:
    """Get the default pcconfig.

    Returns:
        The default pcconfig.
    """
    sys.path.append(os.getcwd())
    return __import__(constants.CONFIG_MODULE)


def get_bun_path():
    """Get the path to the bun executable.

    Returns:
        The path to the bun executable.
    """
    return os.path.expandvars(get_config().BUN_PATH)


def get_app() -> Any:
    """Get the app based on the default config.

    Returns:
        The app based on the default config.
    """
    config = get_config()
    module = ".".join([config.APP_NAME, config.APP_NAME])
    app = __import__(module, fromlist=(constants.APP_VAR,))
    return app


def install_dependencies():
    """Install the dependencies."""
    subprocess.call([get_bun_path(), "install"], cwd=constants.WEB_DIR, stdout=PIPE)


def export_app(app):
    """Zip up the app for deployment.

    Args:
        app: The app.
    """
    app.app.compile(ignore_env=False)
    cmd = r"rm -rf .web/_static; cd .web && bun run export && cd _static  && zip -r ../../frontend.zip ./* && cd ../.. && zip -r backend.zip ./* -x .web/\* ./assets\* ./frontend.zip\* ./backend.zip\*"
    os.system(cmd)


def setup_frontend(app):
    """Set up the frontend.

    Args:
        app: The app.
    """
    # Initialize the web directory if it doesn't exist.
    cp(constants.WEB_TEMPLATE_DIR, constants.WEB_DIR, overwrite=False)

    # Install the frontend dependencies.
    console.rule("[bold]Installing Dependencies")
    install_dependencies()

    # Link the assets folder.
    ln(src=os.path.join("..", constants.APP_ASSETS_DIR), dest=constants.WEB_ASSETS_DIR)

    # Compile the frontend.
    app.app.compile(ignore_env=False)


def run_frontend(app) -> subprocess.Popen:
    """Run the frontend.

    Args:
        app: The app.

    Returns:
        The frontend process.
    """
    setup_frontend(app)
    command = [get_bun_path(), "run", "dev"]
    console.rule("[bold green]App Running")
    return subprocess.Popen(
        command, cwd=constants.WEB_DIR
    )  # stdout=PIPE to hide output


def run_frontend_prod(app) -> subprocess.Popen:
    """Run the frontend.

    Args:
        app: The app.

    Returns:
        The frontend process.
    """
    setup_frontend(app)
    # Export and zip up the frontend and backend then  start the frontend in production mode.
    cmd = r"rm -rf .web/_static || true; cd .web && bun run export"
    os.system(cmd)
    command = [get_bun_path(), "run", "prod"]
    return subprocess.Popen(command, cwd=constants.WEB_DIR)


def run_backend(app):
    """Run the backend.

    Args:
        app: The app.
    """
    command = constants.RUN_BACKEND + [
        f"{app.__name__}:{constants.APP_VAR}.{constants.API_VAR}"
    ]
    subprocess.call(command)


def run_backend_prod(app) -> None:
    """Run the backend.

    Args:
        app: The app.
    """
    command = constants.RUN_BACKEND_PROD + [f"{app.__name__}:{constants.API_VAR}"]
    subprocess.call(command)


def get_production_backend_url() -> str:
    """Get the production backend URL.

    Returns:
        The production backend URL.
    """
    config = get_config()
    return constants.PRODUCTION_BACKEND_URL.format(
        username=config.USERNAME,
        app_name=config.APP_NAME,
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


def to_title(text: str) -> str:
    """Convert a string from snake case to a title.

    Each word is converted to title case and separated by a space.

    Args:
        text: The string to convert.

    Returns:
        The title case string.
    """
    return " ".join(word.capitalize() for word in text.split("_"))


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


def get_page_path(path: str) -> str:
    """Get the path of the compiled JS file for the given page.

    Args:
        path: The path of the page.

    Returns:
        The path of the compiled JS file.
    """
    return os.path.join(constants.WEB_PAGES_DIR, path + constants.JS_EXT)


def get_theme_path() -> str:
    """Get the path of the base theme style.

    Returns:
        The path of the theme style.
    """
    return os.path.join(constants.WEB_UTILS_DIR, constants.THEME + constants.JS_EXT)


def write_page(path: str, code: str):
    """Write the given code to the given path.

    Args:
        path: The path to write the code to.
        code: The code to write.
    """
    mkdir(os.path.dirname(path))
    with open(path, "w") as f:
        f.write(code)


def format_route(route: str):
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


def format_event_fn(fn: Callable) -> str:
    """Format a function as an event.

    Args:
        fn: The function to format.

    Returns:
        The formatted function.
    """
    from pynecone.event import EventHandler

    if isinstance(fn, EventHandler):
        fn = fn.fn
    return fn.__qualname__.replace(".", "_")


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


def format_state(value: Dict) -> Dict:
    """Recursively format values in the given state.

    Args:
        value: The state to format.

    Returns:
        The formatted state.
    """
    if isinstance(value, go.Figure):
        return json.loads(to_json(value))["data"]
    import pandas as pd

    if isinstance(value, pd.DataFrame):
        return {
            "columns": value.columns.tolist(),
            "data": value.values.tolist(),
        }
    if isinstance(value, dict):
        return {k: format_state(v) for k, v in value.items()}
    return value


def get_event(state, event):
    """Get the event from the given state.

    Args:
        state: The state.
        event: The event.

    Returns:
        The event.
    """
    return f"{state.get_name()}.{event}"


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


def get_redis():
    """Get the redis client.

    Returns:
        The redis client.
    """
    try:
        import redis

        config = get_config()
        redis_host, redis_port = config.REDIS_HOST.split(":")
        print("Using redis at", config.REDIS_HOST)
        return redis.Redis(host=redis_host, port=redis_port, db=0)
    except:
        return None
