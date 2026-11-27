"""Namespace for the components that compile to plain HTML and static CSS."""

from __future__ import annotations

from reflex_base.utils import lazy_loader

_SUBMODULES: set[str] = set()

_SUBMOD_ATTRS: lazy_loader.SubmodAttrsType = {
    "layout.box": ["box"],
}

__getattr__, __dir__, __all__ = lazy_loader.attach(
    __name__,
    submodules=_SUBMODULES,
    submod_attrs=_SUBMOD_ATTRS,
)
