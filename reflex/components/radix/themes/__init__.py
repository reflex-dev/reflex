"""Namespace for components provided by the @radix-ui/themes library."""
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
