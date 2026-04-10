"""A sub-package with lazy loading.

This tests __init__.py stub generation with _SUBMOD_ATTRS.
"""

from reflex_base.utils import lazy_loader

_SUBMOD_ATTRS: dict[str, list[str]] = {
    "widget": ["SubWidget"],
}

__getattr__, __dir__, __all__ = lazy_loader.attach(
    __name__,
    submod_attrs=_SUBMOD_ATTRS,
)
