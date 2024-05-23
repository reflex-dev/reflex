"""The el package exports raw HTML elements."""
from . import elements

import lazy_loader as lazy

__getattr__, __dir__, __all__ = lazy.attach(
    __name__,
    submodules={"elements"},
    submod_attrs={f"elements.{k}":v for k,v in elements.MAPPING.items()}
)