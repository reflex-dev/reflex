"""Namespace for components provided by @radix-ui packages."""
import lazy_loader as lazy

from reflex import RADIX_MAPPING

_SUBMODULES: set[str] = {"themes", "primitives"}

_SUBMOD_ATTRS: dict[str, list[str]] = {
    "".join(k.split("components.radix.")[-1]): v for k, v in RADIX_MAPPING.items()
}
__getattr__, __dir__, __all__ = lazy.attach(
    __name__,
    submodules=_SUBMODULES,
    submod_attrs=_SUBMOD_ATTRS,
)
