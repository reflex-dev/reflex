"""Import all the components."""

from __future__ import annotations

from reflex.utils import lazy_loader

_SUBMODULES: set[str] = {
    "lucide",
    "core",
    "datadisplay",
    "gridjs",
    "markdown",
    "moment",
    "plotly",
    "radix",
    "react_player",
    "sonner",
    "suneditor",
    "chakra",
    "el",
    "base",
    "recharts",
}

_SUBMOD_ATTRS: dict[str, list[str]] = {
    "component": [
        "Component",
        "NoSSRComponent",
    ],
    "next": ["NextLink", "next_link"],
}
__getattr__, __dir__, __all__ = lazy_loader.attach(
    __name__,
    submodules=_SUBMODULES,
    submod_attrs=_SUBMOD_ATTRS,
)
