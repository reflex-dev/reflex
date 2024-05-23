"""Import all the components."""
from __future__ import annotations

import lazy_loader as lazy

__getattr__, __dir__, __all__ = lazy.attach(
    __name__,
    submodules={
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
    },
    submod_attrs={
        "component": [
            "Component",
            "NoSSRComponent",
        ],
        "next": ["NextLink", "next_link"],
    },
)
