"""Declarative layout and common spacing props."""
from __future__ import annotations

from typing import Dict, Literal, Optional

from reflex import el
from reflex.vars import Var

from ..base import (
    LiteralAlign,
    LiteralJustify,
    LiteralSpacing,
    RadixThemesComponent,
)

LiteralFlexDirection = Literal["row", "column", "row-reverse", "column-reverse"]
LiteralFlexWrap = Literal["nowrap", "wrap", "wrap-reverse"]


class Flex(el.Div, RadixThemesComponent):
    """Component for creating flex layouts."""

    tag = "Flex"

    # Change the default rendered element for the one passed as a child, merging their props and behavior.
    as_child: Optional[Var[bool]] = None

    # How child items are layed out: "row" | "column" | "row-reverse" | "column-reverse"
    direction: Optional[Var[LiteralFlexDirection]] = None

    # Alignment of children along the main axis: "start" | "center" | "end" | "baseline" | "stretch"
    align: Optional[Var[LiteralAlign]] = None

    # Alignment of children along the cross axis: "start" | "center" | "end" | "between"
    justify: Optional[Var[LiteralJustify]] = None

    # Whether children should wrap when they reach the end of their container: "nowrap" | "wrap" | "wrap-reverse"
    wrap: Optional[Var[LiteralFlexWrap]] = None

    # Gap between children: "0" - "9"
    spacing: Optional[Var[LiteralSpacing]] = None

    # Reflex maps the "spacing" prop to "gap" prop.
    _rename_props: Dict[str, str] = {"spacing": "gap"}
