"""Declarative layout and common spacing props."""

from __future__ import annotations

from reflex_components_core.el import elements

from reflex_components_radix.themes.base import RadixThemesComponent


class Box(elements.Div, RadixThemesComponent):
    """A fundamental layout building block, based on `div` element."""

    tag = "Box"


box = Box.create
