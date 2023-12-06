"""Declarative layout and common spacing props."""
from __future__ import annotations

from typing import Literal

from reflex import el
from reflex.vars import Var

from ..base import (
    LiteralAlign,
    LiteralJustify,
    LiteralSize,
    RadixThemesComponent,
)

LiteralGridDisplay = Literal["none", "inline-grid", "grid"]
LiteralGridFlow = Literal["row", "column", "dense", "row-dense", "column-dense"]


class Grid(el.Div, RadixThemesComponent):
    """Component for creating grid layouts."""

    tag = "Grid"

    # Change the default rendered element for the one passed as a child, merging their props and behavior.
    as_child: Var[bool]

    # How to display the element: "none" | "inline-grid" | "grid"
    display: Var[LiteralGridDisplay]

    # Number of columns
    columns: Var[str]

    # Number of rows
    rows: Var[str]

    # How the grid items are layed out: "row" | "column" | "dense" | "row-dense" | "column-dense"
    flow: Var[LiteralGridFlow]

    # Alignment of children along the main axis: "start" | "center" | "end" | "baseline" | "stretch"
    align: Var[LiteralAlign]

    # Alignment of children along the cross axis: "start" | "center" | "end" | "between"
    justify: Var[LiteralJustify]

    # Gap between children: "0" - "9"
    gap: Var[LiteralSize]

    # Gap between children horizontal: "0" - "9"
    gap_x: Var[LiteralSize]

    # Gap between children vertical: "0" - "9"
    gap_x: Var[LiteralSize]
