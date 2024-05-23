"""Declarative layout and common spacing props."""
from __future__ import annotations

from reflex.components.el import elements

from ..base import RadixThemesComponent


class Box(elements.Div, RadixThemesComponent):
    """A fundamental layout building block, based on `div` element."""

    tag = "Box"


box = Box.create
