"""Namespace for components provided by the @radix-ui/themes library."""
# from .base import theme as theme
# from .base import theme_panel as theme_panel
# from .color_mode import color_mode_var_and_namespace as color_mode
# from . import components
# from . import layout
# from . import typography
# from .components import *
# from .layout import *
# from .typography import *


import lazy_loader as lazy

__getattr__, __dir__, __all__ = lazy.attach(
    __name__,
    submodules={"components", "layout", "typography"},
    submod_attrs={
        "base": [
            "theme",
            "theme_panel",
        ],
        "color_mode": [
            "color_mode",
        ],
    },
)