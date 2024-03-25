"""Declarative layout and common spacing props."""

from __future__ import annotations

from typing import Literal

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
    p: Var[LiteralSpacing]

    # Padding horizontal: "0" - "9"
    px: Var[LiteralSpacing]

    # Padding vertical: "0" - "9"
    py: Var[LiteralSpacing]

    # Padding top: "0" - "9"
    pt: Var[LiteralSpacing]

    # Padding right: "0" - "9"
    pr: Var[LiteralSpacing]

    # Padding bottom: "0" - "9"
    pb: Var[LiteralSpacing]

    # Padding left: "0" - "9"
    pl: Var[LiteralSpacing]

    # Whether the element will take up the smallest possible space: "0" | "1"
    flex_shrink: Var[LiteralBoolNumber]

    # Whether the element will take up the largest possible space: "0" | "1"
    flex_grow: Var[LiteralBoolNumber]
