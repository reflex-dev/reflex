"""Declarative layout and common spacing props."""

from __future__ import annotations

from typing import ClassVar, Literal

from reflex.components.component import field
from reflex.components.core.breakpoints import Responsive
from reflex.components.el import elements
from reflex.components.radix.themes.base import (
    LiteralAlign,
    LiteralJustify,
    LiteralSpacing,
    RadixThemesComponent,
)
from reflex.vars.base import Var

LiteralGridFlow = Literal["row", "column", "dense", "row-dense", "column-dense"]


class Grid(elements.Div, RadixThemesComponent):
    """Component for creating grid layouts."""

    tag = "Grid"

    as_child: Var[bool] = field(
        doc="Change the default rendered element for the one passed as a child, merging their props and behavior."
    )

    columns: Var[Responsive[str]] = field(doc="Number of columns")

    rows: Var[Responsive[str]] = field(doc="Number of rows")

    flow: Var[Responsive[LiteralGridFlow]] = field(
        doc='How the grid items are laid out: "row" | "column" | "dense" | "row-dense" | "column-dense"'
    )

    align: Var[Responsive[LiteralAlign]] = field(
        doc='Alignment of children along the main axis: "start" | "center" | "end" | "baseline" | "stretch"'
    )

    justify: Var[Responsive[LiteralJustify]] = field(
        doc='Alignment of children along the cross axis: "start" | "center" | "end" | "between"'
    )

    spacing: Var[Responsive[LiteralSpacing]] = field(
        doc='Gap between children: "0" - "9"'
    )

    spacing_x: Var[Responsive[LiteralSpacing]] = field(
        doc='Gap between children horizontal: "0" - "9"'
    )

    spacing_y: Var[Responsive[LiteralSpacing]] = field(
        doc='Gap between children vertical: "0" - "9"'
    )

    # Reflex maps the "spacing" prop to "gap" prop.
    _rename_props: ClassVar[dict[str, str]] = {
        "spacing": "gap",
        "spacing_x": "gap_x",
        "spacing_y": "gap_y",
    }


grid = Grid.create
