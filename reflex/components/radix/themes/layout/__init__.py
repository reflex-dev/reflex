"""Layout components."""

from __future__ import annotations

from reflex import RADIX_THEMES_LAYOUT_MAPPING
from reflex.utils import lazy_loader

_SUBMOD_ATTRS: dict[str, list[str]] = {
    "".join(k.split("components.radix.themes.layout.")[-1]): v
    for k, v in RADIX_THEMES_LAYOUT_MAPPING.items()
}


__getattr__, __dir__, __all__ = lazy_loader.attach(
    __name__,
    submod_attrs=_SUBMOD_ATTRS,
)
