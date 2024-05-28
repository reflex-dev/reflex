"""Radix primitive components (https://www.radix-ui.com/primitives)."""
from __future__ import annotations

from reflex import RADIX_PRIMITIVES_MAPPING
from reflex.utils import lazy_loader

_SUBMOD_ATTRS: dict[str, list[str]] = {
    "".join(k.split("components.radix.primitives.")[-1]): v
    for k, v in RADIX_PRIMITIVES_MAPPING.items()
}

__getattr__, __dir__, __all__ = lazy_loader.attach(
    __name__,
    submod_attrs=_SUBMOD_ATTRS,
)
