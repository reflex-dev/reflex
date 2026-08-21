"""Reflex UI: themable components built on base HTML elements and Tailwind CSS.

Components carry no JavaScript framework dependency: they are plain HTML
elements styled with Tailwind classes and themed through CSS custom
properties. Customize them globally with :class:`Theme` (or CSS variables),
per component with Tailwind classes, or opt out entirely with
``unstyled=True``.
"""

from __future__ import annotations

from reflex_base.utils import lazy_loader

_SUBMODULES: set[str] = {"components"}

_SUBMOD_ATTRS: dict[str, list[str]] = {
    "base": ["UIComponent"],
    "styling": ["cn"],
    "theme": ["Theme"],
    "plugin": ["UIComponentsPlugin"],
    "components.accordion": ["accordion"],
    "components.alert": ["alert"],
    "components.avatar": ["avatar"],
    "components.badge": ["badge"],
    "components.button": ["button"],
    "components.card": ["card"],
    "components.checkbox": ["checkbox"],
    "components.dialog": ["dialog"],
    "components.input": ["input"],
    "components.label": ["label"],
    "components.progress": ["progress"],
    "components.radio_group": ["radio_group"],
    "components.select": ["select"],
    "components.separator": ["separator"],
    "components.skeleton": ["skeleton"],
    "components.spinner": ["spinner"],
    "components.switch": ["switch"],
    "components.tabs": ["tabs"],
    "components.textarea": ["textarea"],
}

__getattr__, __dir__, __all__ = lazy_loader.attach(
    __name__,
    submodules=_SUBMODULES,
    submod_attrs=_SUBMOD_ATTRS,
)
