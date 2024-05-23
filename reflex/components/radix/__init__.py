"""Namespace for components provided by @radix-ui packages."""
import lazy_loader as lazy
from reflex import RADIX_MAPPING

__getattr__, __dir__, __all__ = lazy.attach(
    __name__,
    submodules={"themes", "primitives"},
    submod_attrs= {"".join(k.split("components.radix.")[-1]): v for k,v in RADIX_MAPPING.items()}
)