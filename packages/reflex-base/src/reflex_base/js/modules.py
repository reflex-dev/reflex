"""JavaScript modules imported from Python, and calls to their exports.

Each exported function of an imported module becomes a function that returns
an event. The event runs the function in the browser by name: the compiler
copies the module into ``.web`` and ``utils/scripts.js`` loads it by its Python
module name, so only the module name, the function name and the JSON arguments
are sent, and nothing is evaluated.

Internal: what an app relies on is the import itself and the events the
imported functions return, which ``docs/api-reference/browser_javascript.md``
documents.
"""

from __future__ import annotations

import dataclasses
import functools
import inspect
import keyword
from pathlib import Path
from types import ModuleType
from typing import Any, NoReturn

from reflex_base.event import EventHandler, EventSpec, server_side
from reflex_base.js.source import ScriptSource, read_script, strip_query
from reflex_base.registry import RegistrationContext
from reflex_base.utils.exceptions import ReflexRuntimeError
from reflex_base.utils.format import format_event_handler

# The name of the frontend event that calls a function of a module.
_CALL_JS = "_call_js"

# Specifiers that do not name an npm package: relative and absolute paths, the
# app's own modules (`$/`), subpath imports (`#`) and a common path alias
# (`@/`). A specifier with a scheme, such as `virtual:` or `https:`, does not
# either.
_NOT_PACKAGE_PREFIXES = (".", "/", "$/", "#", "@/")
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


def _package_imports(file: Path, imports: list[str]) -> list[str]:
    """Find the npm packages a JavaScript file imports, to install them.

    Args:
        file: The file.
        imports: The specifiers it imports.

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
            packages[strip_query(specifier)] = None
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


def _missing_export(
    module: str, path: Path, script: ScriptSource, name: str
) -> NoReturn:
    """Fail to get a name that a JavaScript module does not export as a function.

    Installed as the module's ``__getattr__``. It raises ImportError, not
    AttributeError, because ``from module import name`` replaces an
    AttributeError with a message of its own, which does not say why.

    Args:
        module: The Python name of the module.
        path: The JavaScript file.
        script: Its source.
        name: The name looked up.

    Raises:
        AttributeError: For a private or special name, which Python and tools
            look up to inspect a module.
        ImportError: For any other name.
    """
    if name.startswith("_"):
        msg = f"module {module!r} has no attribute {name!r}"
        raise AttributeError(msg)
    if name in script.values:
        msg = (
            f"Cannot import {name} from {module}: {path} exports {name} as a "
            "value, not a function, and Python can only call functions. Export "
            f"a function instead, as in `export function {name}() {{ ... }}`."
        )
    else:
        exports = ", ".join(script.functions) or "none"
        msg = (
            f"Cannot import {name} from {module}: {path} exports no function "
            f"named {name} (its functions: {exports}). Export it from "
            f"{path.name}, as in `export function {name}() {{ ... }}`."
        )
    raise ImportError(msg, name=module, path=str(path))


def _load_module(module: ModuleType, path: Path) -> None:
    """Expose the exported functions of a JavaScript file on a Python module.

    Args:
        module: The module being imported.
        path: The JavaScript file.
    """
    script = read_script(path)
    RegistrationContext.ensure_context()._script_modules[module.__name__] = path
    for name in script.functions:
        setattr(module, name, _JsFunction(module.__name__, name))
    setattr(module, "__all__", script.functions)  # noqa: B010
    setattr(  # noqa: B010
        module,
        "__getattr__",
        functools.partial(_missing_export, module.__name__, path, script),
    )


def _render_stub(path: Path, functions: list[str]) -> str:
    """Render a type stub for a JavaScript module, so type checkers see it.

    Exports that are not Python identifiers cannot be imported and are left
    out. The arguments are untyped.

    Args:
        path: The JavaScript file.
        functions: Its exported functions.

    Returns:
        The ``.pyi`` source.
    """
    lines = [
        f"# Generated by Reflex from {path.name}; rewritten when it changes.",
        "from typing import Any",
        "",
        "from reflex_base.event import EventSpec",
        "",
    ]
    lines.extend(
        f"def {name}(*args: Any) -> EventSpec: ..."
        for name in functions
        if name.isidentifier() and not keyword.iskeyword(name)
    )
    return "\n".join(lines) + "\n"
