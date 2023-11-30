"""Declarative layout and common spacing props."""
from __future__ import annotations

from typing import Literal

from reflex import el
from reflex.vars import Var

from ..base import (
    CommonMarginProps,
    LiteralAlign,
    LiteralJustify,
    LiteralSize,
    RadixThemesComponent,
)

from .base import (
    LayoutComponent
)

class Box(el.Div, LayoutComponent):
    """A fundamental layout building block, based on <div>."""

    tag = "Box"