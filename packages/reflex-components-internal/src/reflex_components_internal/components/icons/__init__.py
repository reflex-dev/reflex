"""Icons sub-package."""

from reflex.utils import lazy_loader

_SUBMODULES: set[str] = {
    "hugeicon",
    "others",
}

_SUBMOD_ATTRS: dict[str, list[str]] = {
    "hugeicon": ["hi", "icon"],
    "others": ["spinner", "select_arrow"],
}

__getattr__, __dir__, __all__ = lazy_loader.attach(
    __name__,
    submodules=_SUBMODULES,
    submod_attrs=_SUBMOD_ATTRS,
)
