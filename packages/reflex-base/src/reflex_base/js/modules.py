"""JavaScript modules imported from Python, and calls to their exports.

Each exported function of an imported module becomes a ``JsFunction``. Calling
it returns an event that runs the function in the browser by name: the compiler
copies the module into ``.web`` and re-exports it from ``utils/scripts.js``, so
only the module, the function name and the JSON arguments are sent, and nothing
is evaluated.
"""

from __future__ import annotations

import dataclasses
import inspect
from pathlib import Path
from types import ModuleType
from typing import Any

from reflex_base.event import EventHandler, EventSpec, server_side
from reflex_base.js.source import find_exports, find_imports, strip_query
from reflex_base.registry import RegistrationContext
from reflex_base.utils.format import format_event_handler

# The name of the frontend event that calls a function of a module.
CALL_JS = "_call_js"

# Specifiers that do not name an npm package.
_LOCAL_PREFIXES = (".", "/", "$/", "node:", "http://", "https://")


def find_package_imports(source: str) -> list[str]:
    """Find the npm packages a JavaScript module imports.

    Args:
        source: The module source.

    Returns:
        The import specifiers that name a package, such as ``canvas-confetti``
        or ``@scope/pkg/sub``, without query or fragment, without duplicates.
    """
    return list(
        dict.fromkeys(
            strip_query(specifier)
            for specifier in find_imports(source)
            if not specifier.startswith(_LOCAL_PREFIXES)
        )
    )


def module_key(name: str) -> str:
    """Get the name ``utils/scripts.js`` exports a module under.

    ``$`` cannot occur in a Python module name, so two modules never share one.

    Args:
        name: The dotted Python module name.

    Returns:
        A JavaScript identifier.
    """
    return name.replace(".", "$")


def _call_js(module: str, function: str, args: list) -> None:
    """The signature of the event that calls a function of a module.

    Args:
        module: The module key.
        function: The exported name.
        args: The arguments.
    """


_CALL_JS_SIGNATURE = inspect.signature(_call_js)


@dataclasses.dataclass(frozen=True, slots=True)
class JsFunction:
    """An exported function of a JavaScript module imported from Python."""

    # The dotted name of the module.
    module: str
    # The exported name.
    name: str

    def __call__(self, *args: Any) -> EventSpec:
        """Build the event that calls the function in the browser.

        An event handler argument arrives as its full name, which the
        function can dispatch with ``env.addEvents([env.event(name, payload)])``.

        Args:
            *args: The arguments: values, Vars or event handlers. Values are
                sent as JSON.

        Returns:
            The event.
        """
        return server_side(
            CALL_JS,
            _CALL_JS_SIGNATURE,
            module=module_key(self.module),
            function=self.name,
            args=[
                format_event_handler(arg) if isinstance(arg, EventHandler) else arg
                for arg in args
            ],
        )


def load_module(module: ModuleType, path: Path) -> None:
    """Expose the exports of a JavaScript file on a Python module.

    Args:
        module: The module being imported.
        path: The JavaScript file.
    """
    exports = find_exports(path.read_text(encoding="utf-8"))
    RegistrationContext.ensure_context().script_modules[module.__name__] = path
    for name in exports:
        setattr(module, name, JsFunction(module.__name__, name))
    setattr(module, "__all__", exports)  # noqa: B010
