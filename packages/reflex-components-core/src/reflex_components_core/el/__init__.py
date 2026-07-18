"""The el package exports raw HTML elements."""

from __future__ import annotations

from reflex_base.utils import lazy_loader

from . import elements

_SUBMODULES: set[str] = {"elements"}
_SUBMOD_ATTRS: dict[str, list[str]] = {
    # el.a is replaced by React Router's Link.
    f"elements.{k}": [attr for attr in attrs if attr != "a"]
    for k, attrs in elements._MAPPING.items()
}
_EXTRA_MAPPINGS: dict[str, str] = {
    "a": "reflex_components_core.react_router.link",
}

__getattr__, __dir__, __all__ = lazy_loader.attach(
    __name__,
    submodules=_SUBMODULES,
    submod_attrs=_SUBMOD_ATTRS,
    **_EXTRA_MAPPINGS,
)
