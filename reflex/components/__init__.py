"""Import all the components."""
from __future__ import annotations

# from .el import img as image

import lazy_loader as lazy

__getattr__, __dir__, __all__ = lazy.attach(
    __name__,
    submodules={"lucide", "core", "datadisplay", "gridjs", "markdown", "moment", "plotly", "radix", "react_player", "sonner", "suneditor", "chakra", "el"},
    submod_attrs={
        "base": [
            "Fragment",
            "fragment",
            "Script",
            "fragment",
            "script",
        ],
        "component": [
            "Component",
            "NoSSRComponent",
        ],
        "next": [
            "NextLink",
            "next_link"
        ],
        "el.elements": [
            "img as image",
        ],
    },
)