"""Radix primitive components (https://www.radix-ui.com/primitives)."""
from reflex import RADIX_PRIMITIVES_MAPPING
import lazy_loader as lazy

__getattr__, __dir__, __all__ = lazy.attach(
    __name__,
submod_attrs={"".join(k.split("components.radix.primitives.")[-1]): v for k, v in
                     RADIX_PRIMITIVES_MAPPING.items()}

)

