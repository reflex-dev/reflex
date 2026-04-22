"""Base components sub-package."""

from reflex.utils import lazy_loader
from reflex_ui import _REFLEX_UI_MAPPING

_SUBMODULES = set()
_SUBMOD_ATTRS = {
    "".join(k.split("components.base.")[-1]): v for k, v in _REFLEX_UI_MAPPING.items()
}

__getattr__, __dir__, __all__ = lazy_loader.attach(
    __name__,
    submodules=_SUBMODULES,
    submod_attrs=_SUBMOD_ATTRS,
)
