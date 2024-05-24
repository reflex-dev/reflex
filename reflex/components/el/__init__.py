"""The el package exports raw HTML elements."""
from __future__ import annotations

import lazy_loader as lazy

from . import elements

_SUBMODULES: set[str] = {"elements"}
_SUBMOD_ATTRS: dict[str, list[str]] = {
    f"elements.{k}": v for k, v in elements.MAPPING.items()
}

__getattr__, __dir__, __all__ = lazy.attach(
    __name__,
    submodules=_SUBMODULES,
    submod_attrs=_SUBMOD_ATTRS,
)

