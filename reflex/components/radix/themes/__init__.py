"""Namespace for components provided by the @radix-ui/themes library."""
import lazy_loader as lazy

_SUBMODULES: set[str] = {"components", "layout", "typography"}
_SUBMOD_ATTRS: dict[str, list[str]] = {
    "base": [
        "theme",
        "theme_panel",
    ],
    "color_mode": [
        "color_mode",
    ],
}

__getattr__, __dir__, __all__ = lazy.attach(
    __name__,
    submodules=_SUBMODULES,
    submod_attrs=_SUBMOD_ATTRS,
)
