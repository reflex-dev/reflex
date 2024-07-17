"""Declarative layout and common spacing props."""

from __future__ import annotations

from typing import Literal

from reflex.components.core.breakpoints import Responsive
from reflex.vars import Var

from ..base import (
    CommonMarginProps,
    LiteralSpacing,
    RadixThemesComponent,
)

LiteralBoolNumber = Literal["0", "1"]


class LayoutComponent(CommonMarginProps, RadixThemesComponent):
    """Box, Flex and Grid are foundational elements you'll use to construct
    layouts. Box provides block-level spacing and sizing, while Flex and Grid
    let you create flexible columns, rows and grids.
    """

    # Padding: "0" - "9"
    p: Var[Responsive[LiteralSpacing]]

    # Padding horizontal: "0" - "9"
    px: Var[Responsive[LiteralSpacing]]

    # Padding vertical: "0" - "9"
    py: Var[Responsive[LiteralSpacing]]

    # Padding top: "0" - "9"
    pt: Var[Responsive[LiteralSpacing]]

    # Padding right: "0" - "9"
    pr: Var[Responsive[LiteralSpacing]]

    # Padding bottom: "0" - "9"
    pb: Var[Responsive[LiteralSpacing]]

    # Padding left: "0" - "9"
    pl: Var[Responsive[LiteralSpacing]]

    # Whether the element will take up the smallest possible space: "0" | "1"
    flex_shrink: Var[Responsive[LiteralBoolNumber]]

    # Whether the element will take up the largest possible space: "0" | "1"
    flex_grow: Var[Responsive[LiteralBoolNumber]]
