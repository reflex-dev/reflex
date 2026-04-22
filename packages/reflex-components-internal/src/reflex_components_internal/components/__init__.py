"""Components for Reflex UI."""

from __future__ import annotations

from reflex.utils import lazy_loader

_SUBMODULES: set[str] = {
    "base",
    "icons",
}

_SUBMOD_ATTRS: dict[str, list[str]] = {}

__getattr__, __dir__, __all__ = lazy_loader.attach(
    __name__,
    submodules=_SUBMODULES,
    submod_attrs=_SUBMOD_ATTRS,
)
