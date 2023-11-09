"""Declarative layout and common spacing props."""
from __future__ import annotations

from typing import Literal

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

class Box(LayoutComponent):
    """A fundamental layout building block, based on <div>."""

    tag = "Box"