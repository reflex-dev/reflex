"""Declarative layout and common spacing props."""
from __future__ import annotations

from typing import Literal

from reflex.vars import Var

from ..base import (
    CommonMarginProps,
    LiteralSize,
    RadixThemesComponent,
)

LiteralBoolNumber = Literal["0", "1"]


class LayoutComponent(CommonMarginProps, RadixThemesComponent):
    """Box, Flex and Grid are foundational elements you'll use to construct
    layouts. Box provides block-level spacing and sizing, while Flex and Grid
    let you create flexible columns, rows and grids.
    """

    # Padding: "0" - "9"
    p: Var[LiteralSize]

    # Padding horizontal: "0" - "9"
    px: Var[LiteralSize]

    # Padding vertical: "0" - "9"
    py: Var[LiteralSize]

    # Padding top: "0" - "9"
    pt: Var[LiteralSize]

    # Padding right: "0" - "9"
    pr: Var[LiteralSize]

    # Padding bottom: "0" - "9"
    pb: Var[LiteralSize]

    # Padding left: "0" - "9"
    pl: Var[LiteralSize]

    # Whether the element will take up the smallest possible space: "0" | "1"
    shrink: Var[LiteralBoolNumber]

    # Whether the element will take up the largest possible space: "0" | "1"
    grow: Var[LiteralBoolNumber]
