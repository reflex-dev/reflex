"""Declarative layout and common spacing props."""

from __future__ import annotations

from typing import Dict, Literal

from reflex.components.core.breakpoints import Responsive
from reflex.components.el import elements
from reflex.ivars.base import ImmutableVar

from ..base import (
    LiteralAlign,
    LiteralJustify,
    LiteralSpacing,
    RadixThemesComponent,
)

LiteralGridFlow = Literal["row", "column", "dense", "row-dense", "column-dense"]


class Grid(elements.Div, RadixThemesComponent):
    """Component for creating grid layouts."""

    tag = "Grid"

    # Change the default rendered element for the one passed as a child, merging their props and behavior.
    as_child: ImmutableVar[bool]

    # Number of columns
    columns: ImmutableVar[Responsive[str]]

    # Number of rows
    rows: ImmutableVar[Responsive[str]]

    # How the grid items are layed out: "row" | "column" | "dense" | "row-dense" | "column-dense"
    flow: ImmutableVar[Responsive[LiteralGridFlow]]

    # Alignment of children along the main axis: "start" | "center" | "end" | "baseline" | "stretch"
    align: ImmutableVar[Responsive[LiteralAlign]]

    # Alignment of children along the cross axis: "start" | "center" | "end" | "between"
    justify: ImmutableVar[Responsive[LiteralJustify]]

    # Gap between children: "0" - "9"
    spacing: ImmutableVar[Responsive[LiteralSpacing]]

    # Gap between children horizontal: "0" - "9"
    spacing_x: ImmutableVar[Responsive[LiteralSpacing]]

    # Gap between children vertical: "0" - "9"
    spacing_y: ImmutableVar[Responsive[LiteralSpacing]]

    # Reflex maps the "spacing" prop to "gap" prop.
    _rename_props: Dict[str, str] = {
        "spacing": "gap",
        "spacing_x": "gap_x",
        "spacing_y": "gap_y",
    }


grid = Grid.create
