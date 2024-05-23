"""Typographic components."""


import lazy_loader as lazy

from reflex import RADIX_THEMES_TYPOGRAPHY_MAPPING

__getattr__, __dir__, __all__ = lazy.attach(
    __name__,
    submod_attrs={
        "".join(k.split("components.radix.themes.typography.")[-1]): v
        for k, v in RADIX_THEMES_TYPOGRAPHY_MAPPING.items()
    },
)
