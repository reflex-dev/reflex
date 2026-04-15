"""Layout components."""

from __future__ import annotations

from reflex_base.utils import lazy_loader

from reflex_components_radix.mappings import RADIX_THEMES_LAYOUT_MAPPING

_SUBMOD_ATTRS: lazy_loader.SubmodAttrsType = {
    "".join(k.split("reflex_components_radix.themes.layout.")[-1]): v
    for k, v in RADIX_THEMES_LAYOUT_MAPPING.items()
}


__getattr__, __dir__, __all__ = lazy_loader.attach(
    __name__,
    submod_attrs=_SUBMOD_ATTRS,
)
