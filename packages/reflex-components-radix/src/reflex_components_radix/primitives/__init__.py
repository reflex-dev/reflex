"""Radix primitive components (https://www.radix-ui.com/primitives)."""

from __future__ import annotations

from reflex_base.utils import lazy_loader

from reflex_components_radix.mappings import RADIX_PRIMITIVES_MAPPING

_SUBMOD_ATTRS: lazy_loader.SubmodAttrsType = {
    "".join(k.split("reflex_components_radix.primitives.")[-1]): v
    for k, v in RADIX_PRIMITIVES_MAPPING.items()
} | {"dialog": ["dialog"]}

__getattr__, __dir__, __all__ = lazy_loader.attach(
    __name__,
    submod_attrs=_SUBMOD_ATTRS,
)
