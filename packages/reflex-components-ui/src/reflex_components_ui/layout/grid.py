"""A grid container."""

from __future__ import annotations

from typing import ClassVar, Literal

from reflex_base.components.component import field
from reflex_base.vars.base import Var
from reflex_components_core.core.breakpoints import Responsive
from reflex_components_core.el import elements

from reflex_components_ui.base import UIComponent
from reflex_components_ui.props import LiteralAlign, LiteralJustify, LiteralSpacing
from reflex_components_ui.style import ComponentStyles
from reflex_components_ui.styles.grid import GRID

LiteralGridFlow = Literal["row", "column", "dense", "row-dense", "column-dense"]


class Grid(UIComponent, elements.Div):
    """Component for creating grid layouts."""

    tag = "div"

    styles: ClassVar[ComponentStyles] = GRID

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


grid = Grid.create
