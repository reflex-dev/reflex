"""Namespace for the components that compile to plain HTML and static CSS."""

from __future__ import annotations

from reflex_base.utils import lazy_loader

_SUBMODULES: set[str] = {"tokens"}

_SUBMOD_ATTRS: lazy_loader.SubmodAttrsType = {
    "components.aspect_ratio": ["aspect_ratio"],
    "components.button": ["button"],
    "components.inset": ["inset"],
    "components.separator": ["divider", "separator"],
    "components.spinner": ["spinner"],
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
