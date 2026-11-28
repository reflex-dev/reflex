"""Namespace for the components that compile to plain HTML and static CSS."""

from __future__ import annotations

from reflex_base.utils import lazy_loader

_SUBMODULES: set[str] = {"tokens"}

_SUBMOD_ATTRS: lazy_loader.SubmodAttrsType = {
    "components.accordion": ["accordion"],
    "components.aspect_ratio": ["aspect_ratio"],
    "components.avatar": ["avatar"],
    "components.badge": ["badge"],
    "components.button": ["button"],
    "components.callout": ["callout"],
    "components.card": ["card"],
    "components.checkbox": ["checkbox"],
    "components.checkbox_cards": ["checkbox_cards"],
    "components.checkbox_group": ["checkbox_group"],
    "components.data_list": ["data_list"],
    "components.dialog": ["dialog"],
    "components.form": ["form"],
    "components.icon_button": ["icon_button"],
    "components.inset": ["inset"],
    "components.progress": ["progress"],
    "components.radio_cards": ["radio_cards"],
    "components.radio_group": ["radio", "radio_group"],
    "components.scroll_area": ["scroll_area"],
    "components.segmented_control": ["segmented_control"],
    "components.separator": ["divider", "separator"],
    "components.skeleton": ["skeleton"],
    "components.select": ["select"],
    "components.slider": ["slider"],
    "components.spinner": ["spinner"],
    "components.switch": ["switch"],
    "components.table": ["table"],
    "components.tabs": ["tabs"],
    "components.text_area": ["text_area"],
    "components.text_field": ["input", "text_field"],
    "layout.box": ["box"],
    "layout.center": ["center"],
    "layout.container": ["container"],
    "layout.flex": ["flex"],
    "layout.grid": ["grid"],
    "layout.list": [("list_ns", "list"), "list_item", "ordered_list", "unordered_list"],
    "layout.section": ["section"],
    "layout.spacer": ["spacer"],
    "layout.stack": ["hstack", "stack", "vstack"],
    "layout.theme": ["theme"],
    "themes": ["Theme"],
    "typography.blockquote": ["blockquote"],
    "typography.code": ["code"],
    "typography.heading": ["heading"],
    "typography.link": ["link"],
    "typography.text": ["text"],
}

__getattr__, __dir__, __all__ = lazy_loader.attach(
    __name__,
    submodules=_SUBMODULES,
    submod_attrs=_SUBMOD_ATTRS,
)
