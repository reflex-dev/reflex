"""Reflex internal components package."""

from reflex.utils import lazy_loader

_COMPONENTS_MAPPING = {
    "components.base.accordion": ["accordion"],
    "components.base.avatar": ["avatar"],
    "components.base.badge": ["badge"],
    "components.base.button": ["button"],
    "components.base.card": ["card"],
    "components.base.checkbox": ["checkbox"],
    "components.base.collapsible": ["collapsible"],
    "components.base.context_menu": ["context_menu"],
    "components.base.dialog": ["dialog"],
    "components.base.drawer": ["drawer"],
    "components.base.gradient_profile": ["gradient_profile"],
    "components.base.input": ["input"],
    "components.base.link": ["link"],
    "components.base.menu": ["menu"],
    "components.base.navigation_menu": ["navigation_menu"],
    "components.base.popover": ["popover"],
    "components.base.preview_card": ["preview_card"],
    "components.base.scroll_area": ["scroll_area"],
    "components.base.select": ["select"],
    "components.base.skeleton": ["skeleton"],
    "components.base.slider": ["slider"],
    "components.base.switch": ["switch"],
    "components.base.tabs": ["tabs"],
    "components.base.textarea": ["textarea"],
    "components.base.theme_switcher": ["theme_switcher"],
    "components.base.toggle_group": ["toggle_group"],
    "components.base.toggle": ["toggle"],
    "components.base.tooltip": ["tooltip"],
}

_SUBMODULES = {"components", "utils"}
_SUBMOD_ATTRS = {
    **_COMPONENTS_MAPPING,
    "components": ["base"],
    "components.icons.hugeicon": ["hi", "icon"],
    "components.icons.simple_icon": ["simple_icon"],
    "components.icons.others": ["spinner", "select_arrow", "arrow_svg"],
    "utils.twmerge": ["cn"],
}

__getattr__, __dir__, __all__ = lazy_loader.attach(
    __name__,
    submodules=_SUBMODULES,
    submod_attrs=_SUBMOD_ATTRS,
)
