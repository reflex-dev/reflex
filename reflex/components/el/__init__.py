"""The el package exports raw HTML elements."""

from __future__ import annotations

from reflex.utils import lazy_loader

from . import elements

_SUBMODULES: set[str] = {"elements"}
_SUBMOD_ATTRS: dict[str, list[str]] = {
    # rx.el.a is replaced by React Router's Link.
    f"elements.{k}": [_v for _v in v if _v != "a"]
    for k, v in elements._MAPPING.items()
}
_EXTRA_MAPPINGS: dict[str, str] = {
    "a": "reflex.components.react_router.link",
}

__getattr__, __dir__, __all__ = lazy_loader.attach(
    __name__,
    submodules=_SUBMODULES,
    submod_attrs=_SUBMOD_ATTRS,
    **_EXTRA_MAPPINGS,
)
