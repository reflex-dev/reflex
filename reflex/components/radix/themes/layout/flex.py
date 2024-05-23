"""Declarative layout and common spacing props."""

from __future__ import annotations

from typing import Dict, Literal

from reflex.components.el import elements
from reflex.vars import Var

from ..base import (
    LiteralAlign,
    LiteralJustify,
    LiteralSpacing,
    RadixThemesComponent,
)

LiteralFlexDirection = Literal["row", "column", "row-reverse", "column-reverse"]
LiteralFlexWrap = Literal["nowrap", "wrap", "wrap-reverse"]


class Flex(elements.Div, RadixThemesComponent):
    """Component for creating flex layouts."""

    tag = "Flex"

    # Change the default rendered element for the one passed as a child, merging their props and behavior.
    as_child: Var[bool]

    # How child items are layed out: "row" | "column" | "row-reverse" | "column-reverse"
    direction: Var[LiteralFlexDirection]

    # Alignment of children along the main axis: "start" | "center" | "end" | "baseline" | "stretch"
    align: Var[LiteralAlign]

    # Alignment of children along the cross axis: "start" | "center" | "end" | "between"
    justify: Var[LiteralJustify]

    # Whether children should wrap when they reach the end of their container: "nowrap" | "wrap" | "wrap-reverse"
    wrap: Var[LiteralFlexWrap]

    # Gap between children: "0" - "9"
    spacing: Var[LiteralSpacing]

    # Reflex maps the "spacing" prop to "gap" prop.
    _rename_props: Dict[str, str] = {"spacing": "gap"}


flex = Flex.create
