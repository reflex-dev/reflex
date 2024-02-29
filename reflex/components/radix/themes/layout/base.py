"""Declarative layout and common spacing props."""
from __future__ import annotations

from typing import Literal, Optional

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
    p: Optional[Var[LiteralSpacing]] = None

    # Padding horizontal: "0" - "9"
    px: Optional[Var[LiteralSpacing]] = None

    # Padding vertical: "0" - "9"
    py: Optional[Var[LiteralSpacing]] = None

    # Padding top: "0" - "9"
    pt: Optional[Var[LiteralSpacing]] = None

    # Padding right: "0" - "9"
    pr: Optional[Var[LiteralSpacing]] = None

    # Padding bottom: "0" - "9"
    pb: Optional[Var[LiteralSpacing]] = None

    # Padding left: "0" - "9"
    pl: Optional[Var[LiteralSpacing]] = None

    # Whether the element will take up the smallest possible space: "0" | "1"
    shrink: Optional[Var[LiteralBoolNumber]] = None

    # Whether the element will take up the largest possible space: "0" | "1"
    grow: Optional[Var[LiteralBoolNumber]] = None
