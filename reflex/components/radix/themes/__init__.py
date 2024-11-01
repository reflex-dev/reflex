"""Namespace for components provided by the @radix-ui/themes library."""

from __future__ import annotations

from reflex.utils import lazy_loader

_SUBMODULES: set[str] = {"components", "layout", "typography"}
_SUBMOD_ATTRS: dict[str, list[str]] = {
    "base": [
        "theme",
        "theme_panel",
    ],
    "color_mode": [
        "color_mode",
    ],
}

__getattr__, __dir__, __all__ = lazy_loader.attach(
    __name__,
    submodules=_SUBMODULES,
    submod_attrs=_SUBMOD_ATTRS,
)
