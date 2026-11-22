"""JavaScript modules imported from Python, and calls to their exports.

Importing a module does not read it: each name looked up on it is a function
that returns an event, and the compiler checks that the module exports a
function of every name looked up. The event runs the function in the browser by
name: the compiler copies the module into ``.web`` and ``utils/scripts.js``
loads it by its Python module name, so only the module name, the function name
and the JSON arguments are sent, and nothing is evaluated.

Internal: what an app relies on is the import itself and the events the
imported functions return, which ``docs/api-reference/browser_javascript.md``
documents.
"""

from __future__ import annotations

import dataclasses
import functools
import inspect
from pathlib import Path
from types import ModuleType
from typing import Any

from reflex_base.event import EventHandler, EventSpec, server_side
from reflex_base.registry import RegistrationContext
from reflex_base.utils.exceptions import ReflexRuntimeError
from reflex_base.utils.format import format_event_handler

# The name of the frontend event that calls a function of a module.
_CALL_JS = "_call_js"

# Specifiers, other than relative paths, that do not name an npm package:
# absolute paths, the app's own modules (`$/`), subpath imports (`#`) and a
# common path alias (`@/`). A specifier with a scheme, such as `virtual:` or
# `https:`, does not either.
_NOT_PACKAGE_PREFIXES = ("/", "$/", "#", "@/")
# Node.js built-in modules that no browser provides and no npm package of the
# same name stands in for.
_NODE_BUILTINS = frozenset({
    "async_hooks",
    "child_process",
    "cluster",
    "crypto",
    "dgram",
    "diagnostics_channel",
    "dns",
    "fs",
    "http",
    "http2",
    "https",
    "inspector",
    "module",
    "net",
    "os",
    "perf_hooks",
    "readline",
    "repl",
    "tls",
    "trace_events",
    "tty",
    "v8",
    "vm",
    "wasi",
    "worker_threads",
    "zlib",
})


def _strip_query(specifier: str) -> str:
    """Remove the query and fragment of an import specifier.

    Args:
        specifier: The specifier, such as ``pkg/a.css?inline``.

    Returns:
        The path part, such as ``pkg/a.css``.
    """
    return specifier.split("?", 1)[0].split("#", 1)[0]


def _package_imports(file: Path, imports: list[str]) -> list[str]:
    """Find the npm packages a JavaScript file imports, to install them.

    Args:
        file: The file.
        imports: The specifiers it imports, other than relative paths.

    Returns:
        The specifiers that name a package, such as ``canvas-confetti`` or
        ``@scope/pkg/sub``, without query or fragment, without duplicates.

    Raises:
        ReflexRuntimeError: If it imports a Node.js built-in module, which
            cannot run in the browser.
    """
    packages: dict[str, None] = {}
    for specifier in imports:
        if (
            specifier.startswith("node:")
            or specifier.partition("/")[0] in _NODE_BUILTINS
        ):
            msg = (
                f"The JavaScript file {file} imports {specifier!r}, a Node.js "
                "built-in module, which does not exist in the browser. Remove "
                "the import, and do the work that needs it in a backend event "
                "handler instead."
            )
            raise ReflexRuntimeError(msg)
        if not specifier.startswith(_NOT_PACKAGE_PREFIXES) and ":" not in specifier:
            packages[_strip_query(specifier)] = None
    return list(packages)


def _call_js(module: str, function: str, args: list) -> None:
    """The signature of the event that calls a function of a module.

    Args:
        module: The Python name of the module.
        function: The exported name.
        args: The arguments.
    """


_CALL_JS_SIGNATURE = inspect.signature(_call_js)


@dataclasses.dataclass(frozen=True, slots=True)
class _JsFunction:
    """An exported function of a JavaScript module imported from Python."""

    # The dotted name of the module.
    module: str
    # The exported name.
    name: str

    def __call__(self, *args: Any) -> EventSpec:
        """Build the event that calls the function in the browser.

        An event handler argument arrives as its full name, which the function
        can dispatch with ``reflex.addEvents([reflex.event(name, payload)])``.

        Args:
            *args: The arguments: values, Vars or event handlers. Values are
                sent as JSON.

        Returns:
            The event.
        """
        return server_side(
            _CALL_JS,
            _CALL_JS_SIGNATURE,
            module=self.module,
            function=self.name,
            args=[
                format_event_handler(arg) if isinstance(arg, EventHandler) else arg
                for arg in args
            ],
        )


@dataclasses.dataclass(frozen=True, slots=True)
class _ScriptModule:
    """A JavaScript module imported from Python."""

    # The JavaScript file.
    path: Path
    # The names looked up on the module, which the compiler checks it exports.
    names: set[str] = dataclasses.field(default_factory=set)


def _get_function(module: ModuleType, names: set[str], name: str) -> _JsFunction:
    """Get a function of a JavaScript module by the name Python looks up.

    Installed as the module's ``__getattr__``. The module is not read when it is
    imported, so the name is recorded for the compiler to check, and the
    function is cached on the module.

    Args:
        module: The module.
        names: The names looked up on it so far.
        name: The name looked up.

    Returns:
        The function.

    Raises:
        AttributeError: For a name that is not an identifier, or a special name
            such as ``__path__``, which Python and tools look up to inspect a
            module.
    """
    if name.startswith("__") or not name.isidentifier():
        msg = f"module {module.__name__!r} has no attribute {name!r}"
        raise AttributeError(msg)
    function = _JsFunction(module.__name__, name)
    names.add(name)
    setattr(module, name, function)
    return function


def _load_module(module: ModuleType, path: Path) -> None:
    """Register a JavaScript module, and get its functions on first use.

    Args:
        module: The module being imported.
        path: The JavaScript file.
    """
    script = _ScriptModule(path)
    RegistrationContext.ensure_context()._script_modules[module.__name__] = script
    setattr(  # noqa: B010
        module, "__getattr__", functools.partial(_get_function, module, script.names)
    )
