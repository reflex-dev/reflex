"""Declarative layout and common spacing props."""

from __future__ import annotations

from typing import Literal

from reflex_base.components.component import field
from reflex_base.vars.base import Var
from reflex_components_core.core.breakpoints import Responsive

from reflex_components_radix.themes.base import (
    CommonMarginProps,
    CommonPaddingProps,
    RadixThemesComponent,
)

LiteralBoolNumber = Literal["0", "1"]


class LayoutComponent(CommonMarginProps, CommonPaddingProps, RadixThemesComponent):
    """Box, Flex and Grid are foundational elements you'll use to construct
    layouts. Box provides block-level spacing and sizing, while Flex and Grid
    let you create flexible columns, rows and grids.
    """

    flex_shrink: Var[Responsive[LiteralBoolNumber]] = field(
        doc='Whether the element will take up the smallest possible space: "0" | "1"'
    )

    flex_grow: Var[Responsive[LiteralBoolNumber]] = field(
        doc='Whether the element will take up the largest possible space: "0" | "1"'
    )
