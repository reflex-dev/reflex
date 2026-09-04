"""Namespace for components provided by @radix-ui packages."""

from __future__ import annotations

from reflex_base.utils import lazy_loader

from reflex_components_radix.mappings import RADIX_MAPPING

_SUBMODULES: set[str] = {"themes", "primitives"}

_SUBMOD_ATTRS: lazy_loader.SubmodAttrsType = {
    "".join(k.split("reflex_components_radix.")[-1]): v
    for k, v in RADIX_MAPPING.items()
}
__getattr__, __dir__, __all__ = lazy_loader.attach(
    __name__,
    submodules=_SUBMODULES,
    submod_attrs=_SUBMOD_ATTRS,
)
