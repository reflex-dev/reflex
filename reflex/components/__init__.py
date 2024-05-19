"""Import all the components."""
from __future__ import annotations

# from . import lucide
# from .base import Fragment, Script, fragment, script
# from .component import Component
# from .component import NoSSRComponent as NoSSRComponent
# # from .core import *
# from . import core
# # from .datadisplay import *
# from . import datadisplay
# from .el import img as image
# from . import gridjs
# # from .gridjs import *
# # from .markdown import *
# from . import markdown
# # from .moment import *
# from . import moment
# from .next import NextLink, next_link
# # from .plotly import *
# from . import plotly
# # from .radix import *
# from . import radix
# # from .react_player import *
# from . import react_player
# # from .sonner import *
# from . import sonner
# # from .suneditor import *
# from . import suneditor
#
#
# icon = lucide.icon

import lazy_loader as lazy

__getattr__, __dir__, __all__ = lazy.attach(
    __name__,
    submodules=["lucide", "core", "datadisplay", "gridjs", "markdown", "moment", "plotly", "radix", "react_player", "sonner", "suneditor"],
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
        "el": [
            "img",
        ],
    },
)