"""Namespace for components provided by @radix-ui packages."""

from __future__ import annotations

from reflex import RADIX_MAPPING
from reflex.utils import lazy_loader

_SUBMODULES: set[str] = {"themes", "primitives"}

_SUBMOD_ATTRS: dict[str, list[str]] = {
    "".join(k.split("components.radix.")[-1]): v for k, v in RADIX_MAPPING.items()
}
__getattr__, __dir__, __all__ = lazy_loader.attach(
    __name__,
    submodules=_SUBMODULES,
    submod_attrs=_SUBMOD_ATTRS,
)
