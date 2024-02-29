"""Container to stack elements with spacing."""
from typing import List, Optional

from reflex.components.chakra import ChakraComponent
from reflex.vars import Var


class Grid(ChakraComponent):
    """A grid component."""

    tag = "Grid"

    # Shorthand prop for gridAutoColumns to provide automatic column sizing based on content.
    # Learn more _[here](https://developer.mozilla.org/en-US/docs/Web/CSS/grid-auto-columns)_
    auto_columns: Optional[Var[str]] = None

    # Shorthand prop for gridAutoFlow to specify exactly how
    # auto-placed items get flowed into the grid.
    # Learn more _[here](https://developer.mozilla.org/en-US/docs/Web/CSS/grid-auto-flow)_
    auto_flow: Optional[Var[str]] = None

    # Shorthand prop for gridAutoRows.
    # Learn more _[here](https://developer.mozilla.org/en-US/docs/Web/CSS/grid-auto-rows)_
    auto_rows: Optional[Var[str]] = None

    # Shorthand prop for gridColumn.
    # Learn more _[here](https://developer.mozilla.org/en-US/docs/Web/CSS/grid-column)_
    column: Optional[Var[str]] = None

    # Shorthand prop for gridRow.
    # Learn more _[here](https://developer.mozilla.org/en-US/docs/Web/CSS/grid-row)_
    row: Optional[Var[str]] = None

    # Shorthand prop for gridTemplateColumns.
    # Learn more _[here](https://developer.mozilla.org/en-US/docs/Web/CSS/grid-template-columns)_
    template_columns: Optional[Var[str]] = None

    # Shorthand prop for gridTemplateRows.
    # Learn more _[here](https://developer.mozilla.org/en-US/docs/Web/CSS/grid-template-rows)_
    template_rows: Optional[Var[str]] = None


class GridItem(ChakraComponent):
    """Used as a child of Grid to control the span, and start positions within the grid."""

    tag = "GridItem"

    # Shorthand prop for gridArea
    # Learn more _[here](https://developer.mozilla.org/en-US/docs/Web/CSS/grid-area)_
    area: Optional[Var[str]] = None

    # Shorthand prop for gridColumnEnd
    # Learn more _[here](https://developer.mozilla.org/en-US/docs/Web/CSS/grid-column-end)_
    col_end: Optional[Var[str]] = None

    # The column number the grid item should start.
    col_start: Optional[Var[int]] = None

    # The number of columns the grid item should span.
    col_span: Optional[Var[int]] = None

    # Shorthand prop for gridRowEnd
    # Learn more _[here](https://developer.mozilla.org/en-US/docs/Web/CSS/grid-row-end)_
    row_end: Optional[Var[str]] = None

    # The row number the grid item should start.
    row_start: Optional[Var[int]] = None

    # The number of rows the grid item should span.
    row_span: Optional[Var[int]] = None


class ResponsiveGrid(ChakraComponent):
    """A responsive grid component."""

    tag = "SimpleGrid"

    # Shorthand prop for gridAutoColumns to provide automatic column sizing based on content.
    # Learn more _[here](https://developer.mozilla.org/en-US/docs/Web/CSS/grid-auto-columns)_
    auto_columns: Optional[Var[str]] = None

    # Shorthand prop for gridAutoFlow to specify exactly how
    # auto-placed items get flowed into the grid.
    # Learn more _[here](https://developer.mozilla.org/en-US/docs/Web/CSS/grid-auto-flow)_
    auto_flow: Optional[Var[str]] = None

    # Shorthand prop for gridAutoRows.
    # Learn more _[here](https://developer.mozilla.org/en-US/docs/Web/CSS/grid-auto-rows)_
    auto_rows: Optional[Var[str]] = None

    # Shorthand prop for gridColumn.
    # Learn more _[here](https://developer.mozilla.org/en-US/docs/Web/CSS/grid-column)_
    column: Optional[Var[str]] = None

    # Shorthand prop for gridRow.
    # Learn more _[here](https://developer.mozilla.org/en-US/docs/Web/CSS/grid-row)_
    row: Optional[Var[str]] = None

    # A list that defines the number of columns for each breakpoint.
    columns: Optional[Var[List[int]]] = None

    # The width at which child elements will break into columns. Pass a number for pixel values or a string for any other valid CSS length.
    min_child_width: Optional[Var[str]] = None

    # The gap between the grid items
    spacing: Optional[Var[str]] = None

    # The column gap between the grid items
    spacing_x: Optional[Var[str]] = None

    # The row gap between the grid items
    spacing_y: Optional[Var[str]] = None

    # Shorthand prop for gridTemplateAreas
    # Learn more _[here](https://developer.mozilla.org/en-US/docs/Web/CSS/grid-template-areas)_
    template_areas: Optional[Var[str]] = None

    # Shorthand prop for gridTemplateColumns.
    # Learn more _[here](https://developer.mozilla.org/en-US/docs/Web/CSS/grid-template-columns)_
    template_columns: Optional[Var[str]] = None

    # Shorthand prop for gridTemplateRows.
    # Learn more _[here](https://developer.mozilla.org/en-US/docs/Web/CSS/grid-template-rows)_
    template_rows: Optional[Var[str]] = None
