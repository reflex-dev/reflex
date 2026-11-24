"""JavaScript modules imported from Python, and calls to their exports.

Importing a module does not read it: each name looked up on it is an event
handler for the function of that name, and the compiler checks that the module
exports a function of every name looked up. The event runs the function in the
browser by name: the compiler links the app package into ``.web`` and
``utils/scripts.js`` loads it by its Python module name, so only the module
name, the function name and the JSON arguments are sent, and nothing is
evaluated.

The compiler finds the modules in ``sys.modules``, not in the registration
context: Python runs a module once per process, so an app compiled again in a
new context, as ``AppHarness`` does, imports none of them anew.

Internal: what an app relies on is the import itself and the events the
imported functions return, which ``docs/api-reference/browser_javascript.md``
documents.
"""

from __future__ import annotations

import dataclasses
import functools
import keyword
import sys
from pathlib import Path
from types import ModuleType
from typing import Any, Self

from reflex_base.event import EventHandler, EventSpec
from reflex_base.event.context import EventContext
from reflex_base.js.finder import _app_package
from reflex_base.utils.exceptions import ReflexRuntimeError
from reflex_base.utils.format import format_event_handler
from reflex_base.vars.base import LiteralVar, Var

# The attribute of a JavaScript module that holds what the compiler reads of it.
_SCRIPT_MODULE = "__reflex_script_module__"

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
    """The frontend event that calls a function of a module, named after it.

    Args:
        module: The Python name of the module.
        function: The exported name.
        args: The arguments.
    """


_CALL_JS = EventHandler(fn=_call_js)


def _js_function(*args: Any) -> None:
    """Take any number of arguments, as a JavaScript function does.

    The parameters of each function of a module, which an event trigger checks
    its arguments against.

    Args:
        *args: The arguments.
    """


def _js_argument(value: Any) -> Any:
    """Convert an argument of a function to the value the function receives.

    Args:
        value: The argument.

    Returns:
        For an event handler, its full name; for a bound event, the event
        ``{name, payload}``, with its ``event_actions`` if it has any; for a
        list, tuple or dict, a list or dict of its items converted; else the
        argument.
    """
    if isinstance(value, EventHandler):
        return format_event_handler(value)
    if isinstance(value, EventSpec):
        event = {
            "name": format_event_handler(value.handler),
            "payload": {key._js_expr: arg for key, arg in value.args},
        }
        if value.event_actions:
            event["event_actions"] = value.event_actions
        return event
    if type(value) in (list, tuple):
        return [_js_argument(item) for item in value]
    if type(value) is dict:
        return {key: _js_argument(item) for key, item in value.items()}
    return value


@dataclasses.dataclass(frozen=True)
class _JsFunction(EventHandler):
    """An exported function of a JavaScript module imported from Python.

    An event handler whose event runs the function in the browser, so it works
    wherever an event handler does: an event trigger or a ``callback`` passes
    it its arguments, and ``rx.cond`` or an event handler that returns it calls
    it with none.
    """

    # The dotted name of the module.
    module: str
    # The exported name.
    name: str
    # The parameters, which take any number of arguments.
    fn: Any = dataclasses.field(default=_js_function, kw_only=True, repr=False)

    def __hash__(self) -> int:
        """Hash the function by its module, name and event actions.

        Returns:
            The hash.
        """
        return hash((self.module, self.name, tuple(self.event_actions.items())))

    def __set_name__(self, owner: type, name: str) -> None:
        """Stay unbound on a class: the function belongs to its module.

        Args:
            owner: The class.
            name: The attribute name.
        """

    def __get__(self, instance: Any, owner: type | None = None) -> Self:
        """Read back as the function from a class or its instances.

        Args:
            instance: The instance it is read on, or None.
            owner: The class it is read through.

        Returns:
            This function.
        """
        return self

    def __call__(self, *args: Any) -> EventSpec:
        """Build the event that calls the function in the browser.

        An event handler argument arrives as its full name, which the function
        can dispatch with ``reflex.addEvents([reflex.event(name, payload)])``,
        and a bound event as the event, which it can dispatch with
        ``reflex.addEvents([event])``, also inside a list or a dict.

        Args:
            *args: The arguments: values, Vars, event handlers or bound events.
                Values are sent as JSON.

        Returns:
            The event, with the function's event actions.
        """
        return EventSpec(
            handler=_CALL_JS,
            args=(
                (Var(_js_expr="module"), LiteralVar.create(self.module)),
                (Var(_js_expr="function"), LiteralVar.create(self.name)),
                (
                    Var(_js_expr="args"),
                    LiteralVar.create([_js_argument(arg) for arg in args]),
                ),
            ),
            event_actions=self.event_actions.copy(),
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

    Raises:
        ReflexRuntimeError: If an event handler runs, which is after the app
            compiled, so the frontend does not include the module.
    """
    try:
        in_event = bool(EventContext.get().txid)
    except LookupError:
        in_event = False
    if in_event:
        msg = (
            f"The JavaScript module {module.__name__} is first imported while an "
            "event handler runs, after the app compiled, so the frontend does not "
            "include it. Import it at the top of a Python module that the app "
            "imports when it loads, such as the module that defines the event "
            "handler."
        )
        raise ReflexRuntimeError(msg)
    script = _ScriptModule(path)
    setattr(module, _SCRIPT_MODULE, script)
    setattr(  # noqa: B010
        module, "__getattr__", functools.partial(_get_function, module, script.names)
    )


def _app_modules() -> dict[str, _ScriptModule]:
    """Get the JavaScript modules of the app's package that are imported.

    Returns:
        The modules, by name, in the order of their names.
    """
    prefix = _app_package() + "."
    return dict(
        sorted(
            (name, script)
            # A copy: another thread may import while this one reads.
            for name, module in tuple(sys.modules.items())
            if name.startswith(prefix)
            and (script := getattr(module, _SCRIPT_MODULE, None)) is not None
        )
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
