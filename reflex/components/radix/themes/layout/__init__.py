"""Layout components."""
import lazy_loader as lazy

from reflex import RADIX_THEMES_LAYOUT_MAPPING

_SUBMOD_ATTRS: dict[str, list[str]] = {
    "".join(k.split("components.radix.themes.layout.")[-1]): v
    for k, v in RADIX_THEMES_LAYOUT_MAPPING.items()
}


__getattr__, __dir__, __all__ = lazy.attach(
    __name__,
    submod_attrs=_SUBMOD_ATTRS,
)
