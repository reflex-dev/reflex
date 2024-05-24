"""Radix primitive components (https://www.radix-ui.com/primitives)."""
import lazy_loader as lazy

from reflex import RADIX_PRIMITIVES_MAPPING

_SUBMOD_ATTRS: dict[str, list[str]] = {
    "".join(k.split("components.radix.primitives.")[-1]): v
    for k, v in RADIX_PRIMITIVES_MAPPING.items()
}

__getattr__, __dir__, __all__ = lazy.attach(
    __name__,
    submod_attrs=_SUBMOD_ATTRS,
)
