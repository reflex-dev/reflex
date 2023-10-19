"""Declarative layout and common spacing props."""
from __future__ import annotations

from typing import Literal

from reflex.vars import Var

from .base import (
    CommonMarginProps,
    LiteralAlign,
    LiteralJustify,
    LiteralSize,
    RadixThemesComponent,
)

LiteralBoolNumber = Literal["0", "1"]


class LayoutComponent(CommonMarginProps, RadixThemesComponent):
    """Box, Flex and Grid are foundational elements you'll use to construct
    layouts. Box provides block-level spacing and sizing, while Flex and Grid
    let you create flexible columns, rows and grids.
    """

    # Padding: "0" - "9"
    p: Var[LiteralSize]

    # Padding horizontal: "0" - "9"
    px: Var[LiteralSize]

    # Padding vertical: "0" - "9"
    py: Var[LiteralSize]

    # Padding top: "0" - "9"
    pt: Var[LiteralSize]

    # Padding right: "0" - "9"
    pr: Var[LiteralSize]

    # Padding bottom: "0" - "9"
    pb: Var[LiteralSize]

    # Padding left: "0" - "9"
    pl: Var[LiteralSize]

    # Whether the element will take up the smallest possible space: "0" | "1"
    shrink: Var[LiteralBoolNumber]

    # Whether the element will take up the largest possible space: "0" | "1"
    grow: Var[LiteralBoolNumber]


class Box(LayoutComponent):
    """A fundamental layout building block, based on <div>."""

    tag = "Box"


LiteralFlexDirection = Literal["row", "column", "row-reverse", "column-reverse"]
LiteralFlexDisplay = Literal["none", "inline-flex", "flex"]
LiteralFlexWrap = Literal["nowrap", "wrap", "wrap-reverse"]


class Flex(LayoutComponent):
    """Component for creating flex layouts."""

    tag = "Flex"

    # Change the default rendered element for the one passed as a child, merging their props and behavior.
    as_child: Var[bool]

    # How to display the element: "none" | "inline-flex" | "flex"
    display: Var[LiteralFlexDisplay]

    # How child items are layed out: "row" | "column" | "row-reverse" | "column-reverse"
    direction: Var[LiteralFlexDirection]

    # Alignment of children along the main axis: "start" | "center" | "end" | "baseline" | "stretch"
    align: Var[LiteralAlign]

    # Alignment of children along the cross axis: "start" | "center" | "end" | "between"
    justify: Var[LiteralJustify]

    # Whether children should wrap when they reach the end of their container: "nowrap" | "wrap" | "wrap-reverse"
    wrap: Var[LiteralFlexWrap]

    # Gap between children: "0" - "9"
    gap: Var[LiteralSize]


LiteralGridDisplay = Literal["none", "inline-grid", "grid"]
LiteralGridFlow = Literal["row", "column", "dense", "row-dense", "column-dense"]


class Grid(RadixThemesComponent):
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


LiteralContainerSize = Literal["1", "2", "3", "4"]


class Container(LayoutComponent):
    """Constrains the maximum width of page content.

    See https://www.radix-ui.com/themes/docs/components/container
    """

    tag = "Container"

    # The size of the container: "1" - "4" (default "4")
    size: Var[LiteralContainerSize]


LiteralSectionSize = Literal["1", "2", "3"]


class Section(LayoutComponent):
    """Denotes a section of page content."""

    tag = "Section"

    # The size of the section: "1" - "3" (default "3")
    size: Var[LiteralSectionSize]
