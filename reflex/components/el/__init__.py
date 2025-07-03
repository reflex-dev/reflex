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

__getattr__, __dir__, __all__ = lazy_loader.attach(
    __name__,
    submodules=_SUBMODULES,
    submod_attrs=_SUBMOD_ATTRS,
    extra_all=["a"],
)

# Replace the base `rx.el.a` with React Router's `Link` for client-side navigation.
from reflex.components.react_router import link as a  # noqa: E402
