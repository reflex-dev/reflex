"""Import all the components.

Components have been split across multiple packages.
This module installs an import redirect hook so that
``from reflex.components.<subpkg> import X`` continues to work
by delegating to the appropriate package.
"""

from __future__ import annotations

import importlib
import importlib.abc
import importlib.machinery
import sys
from types import ModuleType

from reflex.utils import lazy_loader

# Mapping from subpackage name to the target top-level package.
_SUBPACKAGE_TARGETS: dict[str, str] = {
    # reflex-components (base package)
    "base": "reflex_components.base",
    "core": "reflex_components.core",
    "datadisplay": "reflex_components.datadisplay",
    "el": "reflex_components.el",
    "gridjs": "reflex_components.gridjs",
    "lucide": "reflex_components.lucide",
    "moment": "reflex_components.moment",
    # reflex-radix
    "radix": "reflex_radix",
    # reflex-markdown
    "markdown": "reflex_markdown",
    # reflex-plotly
    "plotly": "reflex_plotly",
    # reflex-react-player
    "react_player": "reflex_react_player",
    # reflex-react-router
    "react_router": "reflex_react_router",
    # reflex-recharts
    "recharts": "reflex_recharts",
    # reflex-sonner
    "sonner": "reflex_sonner",
}


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
    """Import hook: redirects ``reflex.components.<subpkg>`` to the real package."""

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
            and parts[2] in _SUBPACKAGE_TARGETS
        ):
            base = _SUBPACKAGE_TARGETS[parts[2]]
            rest = ".".join(parts[3:])
            target_name = f"{base}.{rest}" if rest else base
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
    """Resolve attributes: first try local lazy loader, then delegate to component packages.

    Returns:
        The requested attribute from this module or a component package.

    Raises:
        AttributeError: If the attribute is not found.
    """
    try:
        return _lazy_getattr(name)
    except AttributeError:
        pass
    if name in _SUBPACKAGE_TARGETS:
        return importlib.import_module(_SUBPACKAGE_TARGETS[name])
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)
