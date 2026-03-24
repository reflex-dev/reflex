"""Import all the components.

Components have been moved to the ``reflex_components`` package.
This module re-exports them for backwards compatibility and installs
an import redirect hook so that ``from reflex.components.<subpkg> import X``
continues to work by delegating to ``reflex_components.<subpkg>``.
"""

from __future__ import annotations

import importlib
import importlib.abc
import importlib.machinery
import sys
from types import ModuleType

from reflex.utils import lazy_loader

# Subpackages that have moved to the reflex_components package.
_MOVED_SUBMODULES: frozenset[str] = frozenset({
    "base",
    "core",
    "datadisplay",
    "el",
    "gridjs",
    "lucide",
    "markdown",
    "moment",
    "plotly",
    "radix",
    "react_player",
    "react_router",
    "recharts",
    "sonner",
})


class _AliasLoader(importlib.abc.Loader):
    """Loader that aliases one module name to another."""

    def __init__(self, target_name: str):
        self.target_name = target_name

    def create_module(self, spec: importlib.machinery.ModuleSpec) -> ModuleType | None:
        return None

    def exec_module(self, module: ModuleType) -> None:
        target = importlib.import_module(self.target_name)
        # Make the alias point to the real module.
        module.__dict__.update(target.__dict__)
        module.__path__ = getattr(target, "__path__", [])
        module.__file__ = getattr(target, "__file__", None)
        module.__loader__ = self
        # Register the target module under the alias name so subsequent
        # imports resolve immediately.
        sys.modules[module.__name__] = target


class _ComponentsRedirect(importlib.abc.MetaPathFinder):
    """Import hook: redirects ``reflex.components.<moved>`` to ``reflex_components.<moved>``."""

    def find_spec(
        self,
        fullname: str,
        path: object = None,
        target: object = None,
    ) -> importlib.machinery.ModuleSpec | None:
        parts = fullname.split(".")
        if (
            len(parts) >= 3
            and parts[0] == "reflex"
            and parts[1] == "components"
            and parts[2] in _MOVED_SUBMODULES
        ):
            target_name = "reflex_components." + ".".join(parts[2:])
            return importlib.machinery.ModuleSpec(
                fullname,
                _AliasLoader(target_name),
                is_package=True,
            )
        return None


# Install the import redirect hook.
if not any(isinstance(f, _ComponentsRedirect) for f in sys.meta_path):
    sys.meta_path.insert(0, _ComponentsRedirect())


# Submodules that still live in reflex.components (infrastructure).
_SUBMOD_ATTRS: dict[str, list[str]] = {
    "component": [
        "Component",
        "NoSSRComponent",
    ],
}

_lazy_getattr, __dir__, __all__ = lazy_loader.attach(
    __name__,
    submodules=set(),
    submod_attrs=_SUBMOD_ATTRS,
)


def __getattr__(name: str) -> object:
    """Resolve attributes: first try local lazy loader, then delegate to reflex_components.

    Returns:
        The requested attribute from this module or reflex_components.

    Raises:
        AttributeError: If the attribute is not found in either this module or reflex_components.
    """
    try:
        return _lazy_getattr(name)
    except AttributeError:
        pass
    if name in _MOVED_SUBMODULES:
        import reflex_components

        return getattr(reflex_components, name)
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)
