"""Import all the components.

Components have been split across multiple packages.
This module installs an import redirect hook so that
``from reflex_base.components.<subpkg> import X`` continues to work
by delegating to the appropriate package.
"""

from __future__ import annotations

import importlib
import importlib.abc
import importlib.machinery
import sys
from types import ModuleType

from reflex_base.utils import lazy_loader

# Mapping from subpackage name to the target top-level package.
_SUBPACKAGE_TARGETS: dict[str, str] = {
    # reflex-components (base package)
    "base": "reflex_components_core.base",
    "core": "reflex_components_core.core",
    "datadisplay": "reflex_components_core.datadisplay",
    "el": "reflex_components_core.el",
    # Standalone packages
    "gridjs": "reflex_components_gridjs",
    "lucide": "reflex_components_lucide",
    "markdown": "reflex_components_markdown",
    "moment": "reflex_components_moment",
    "plotly": "reflex_components_plotly",
    "radix": "reflex_components_radix",
    "react_player": "reflex_components_react_player",
    "react_router": "reflex_components_core.react_router",
    "recharts": "reflex_components_recharts",
    "sonner": "reflex_components_sonner",
}

# Deeper overrides for subpackages that were split from datadisplay.
# Checked before the general _SUBPACKAGE_TARGETS mapping.
_DEEP_OVERRIDES: dict[str, str] = {
    "datadisplay.code": "reflex_components_code.code",
    "datadisplay.shiki_code_block": "reflex_components_code.shiki_code_block",
    "datadisplay.dataeditor": "reflex_components_dataeditor.dataeditor",
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
        if len(parts) >= 3 and parts[0] == "reflex" and parts[1] == "components":
            subpkg = parts[2]
            rest_parts = parts[3:]

            # Check deep overrides first (e.g. datadisplay.code -> reflex_components_code.code).
            if rest_parts:
                deep_key = f"{subpkg}.{rest_parts[0]}"
                override = _DEEP_OVERRIDES.get(deep_key)
                if override is not None:
                    extra = ".".join(rest_parts[1:])
                    target_name = f"{override}.{extra}" if extra else override
                    return importlib.machinery.ModuleSpec(
                        fullname,
                        _AliasLoader(target_name),
                        is_package=True,
                    )

            # General subpackage mapping.
            if subpkg in _SUBPACKAGE_TARGETS:
                base = _SUBPACKAGE_TARGETS[subpkg]
                rest = ".".join(rest_parts)
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
