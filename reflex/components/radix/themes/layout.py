"""Declarative layout and common spacing props."""
from __future__ import annotations

from reflex.vars import Var

from .base import CommonMarginProps, RadixThemesComponent


class LayoutComponent(CommonMarginProps, RadixThemesComponent):
    """Box, Flex and Grid are foundational elements you'll use to construct
    layouts. Box provides block-level spacing and sizing, while Flex and Grid
    let you create flexible columns, rows and grids.
    """

    # Padding: "0" - "9"
    p: Var[str]

    # Padding horizontal: "0" - "9"
    px: Var[str]

    # Padding vertical: "0" - "9"
    py: Var[str]

    # Padding top: "0" - "9"
    pt: Var[str]

    # Padding right: "0" - "9"
    pr: Var[str]

    # Padding bottom: "0" - "9"
    pb: Var[str]

    # Padding left: "0" - "9"
    pl: Var[str]

    # Whether the element will take up the smallest possible space: "0" | "1"
    shrink: Var[str]

    # Whether the element will take up the largest possible space: "0" | "1"
    grow: Var[str]


class Box(LayoutComponent):
    """A fundamental layout building block, based on <div>."""

    tag = "Box"


class Flex(LayoutComponent):
    """Component for creating flex layouts."""

    tag = "Flex"

    # Change the default rendered element for the one passed as a child, merging their props and behavior.
    as_child: Var[bool]

    # How to display the element: "none" | "inline-flex" | "flex"
    display: Var[str]

    # How child items are layed out: "row" | "column" | "row-reverse" | "column-reverse"
    direction: Var[str]

    # Alignment of children along the main axis: "start" | "center" | "end" | "baseline" | "stretch"
    align: Var[str]

    # Alignment of children along the cross axis: "start" | "center" | "end" | "between"
    justify: Var[str]

    # Whether children should wrap when they reach the end of their container: "nowrap" | "wrap" | "wrap-reverse"
    wrap: Var[str]

    # Gap between children: "0" - "9"
    gap: Var[str]


class Grid(RadixThemesComponent):
    """Component for creating grid layouts."""

    # Change the default rendered element for the one passed as a child, merging their props and behavior.
    as_child: Var[bool]

    # How to display the element: "none" | "inline-grid" | "grid"
    display: Var[str]

    # Number of columns
    columns: Var[str]

    # Number of rows
    rows: Var[str]

    # How the grid items are layed out: "row" | "column" | "dense" | "row-dense" | "column-dense"
    flow: Var[str]

    # Alignment of children along the main axis: "start" | "center" | "end" | "baseline" | "stretch"
    align: Var[str]

    # Alignment of children along the cross axis: "start" | "center" | "end" | "between"
    justify: Var[str]

    # Gap between children: "0" - "9"
    gap: Var[str]

    # Gap between children horizontal: "0" - "9"
    gap_x: Var[str]

    # Gap between children vertical: "0" - "9"
    gap_x: Var[str]


class Container(LayoutComponent):
    """Constrains the maximum width of page content.

    See https://www.radix-ui.com/themes/docs/components/container
    """

    # The size of the container: "1" - "4" (default "4")
    size: Var[str]


class Section(LayoutComponent):
    """Denotes a section of page content."""

    # The size of the section: "1" - "3" (default "3")
    size: Var[str]
