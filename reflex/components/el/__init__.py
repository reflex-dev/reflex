"""The el package exports raw HTML elements."""

from __future__ import annotations

from reflex.utils import lazy_loader

from . import elements

_SUBMODULES: set[str] = {"elements"}
_SUBMOD_ATTRS: dict[str, list[str]] = {
    f"elements.{k}": v for k, v in elements._MAPPING.items()
}
_PYRIGHT_IGNORE_IMPORTS = elements._PYRIGHT_IGNORE_IMPORTS

__getattr__, __dir__, __all__ = lazy_loader.attach(
    __name__,
    submodules=_SUBMODULES,
    submod_attrs=_SUBMOD_ATTRS,
)
