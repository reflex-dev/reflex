"""Declarative layout and common spacing props."""
from __future__ import annotations

from reflex import el

from ..base import RadixThemesComponent


class Box(el.Div, RadixThemesComponent):
    """A fundamental layout building block, based on `div` element."""

    tag = "Box"
