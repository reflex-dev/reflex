"""Typographic components."""


from reflex import RADIX_THEMES_TYPOGRAPHY_MAPPING
import lazy_loader as lazy

__getattr__, __dir__, __all__ = lazy.attach(
    __name__,
submod_attrs={"".join(k.split("components.radix.themes.typography.")[-1]): v for k, v in
                     RADIX_THEMES_TYPOGRAPHY_MAPPING.items()}

)
