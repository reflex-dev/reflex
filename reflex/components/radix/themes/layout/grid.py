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

LiteralGridFlow = Literal["row", "column", "dense", "row-dense", "column-dense"]


class Grid(el.Div, RadixThemesComponent):
    """Component for creating grid layouts."""

    tag: str = "Grid"

    # Change the default rendered element for the one passed as a child, merging their props and behavior.
    as_child: Optional[Var[bool]] = None

    # Number of columns
    columns: Optional[Var[str]] = None

    # Number of rows
    rows: Optional[Var[str]] = None

    # How the grid items are layed out: "row" | "column" | "dense" | "row-dense" | "column-dense"
    flow: Optional[Var[LiteralGridFlow]] = None

    # Alignment of children along the main axis: "start" | "center" | "end" | "baseline" | "stretch"
    align: Optional[Var[LiteralAlign]] = None

    # Alignment of children along the cross axis: "start" | "center" | "end" | "between"
    justify: Optional[Var[LiteralJustify]] = None

    # Gap between children: "0" - "9"
    spacing: Optional[Var[LiteralSpacing]] = None

    # Gap between children horizontal: "0" - "9"
    spacing_x: Optional[Var[LiteralSpacing]] = None

    # Gap between children vertical: "0" - "9"
    spacing_y: Optional[Var[LiteralSpacing]] = None

    # Reflex maps the "spacing" prop to "gap" prop.
    _rename_props: Dict[str, str] = {
        "spacing": "gap",
        "spacing_x": "gap_x",
        "spacing_y": "gap_y",
    }
