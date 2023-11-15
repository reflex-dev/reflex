"""Container to stack elements with spacing."""

from typing import List

from nextpy.components.libs.chakra import ChakraComponent
from nextpy.core.vars import Var


class Grid(ChakraComponent):
    """A grid component."""

    tag = "Grid"

    # Shorthand prop for gridAutoColumns to provide automatic column sizing based on content.
    # Learn more _[here](https://developer.mozilla.org/en-US/docs/Web/CSS/grid-auto-columns)_
    auto_columns: Var[str]

    # Shorthand prop for gridAutoFlow to specify exactly how
    # auto-placed items get flowed into the grid.
    # Learn more _[here](https://developer.mozilla.org/en-US/docs/Web/CSS/grid-auto-flow)_
    auto_flow: Var[str]

    # Shorthand prop for gridAutoRows.
    # Learn more _[here](https://developer.mozilla.org/en-US/docs/Web/CSS/grid-auto-rows)_
    auto_rows: Var[str]

    # Shorthand prop for gridColumn.
    # Learn more _[here](https://developer.mozilla.org/en-US/docs/Web/CSS/grid-column)_
    column: Var[str]

    # Shorthand prop for gridRow.
    # Learn more _[here](https://developer.mozilla.org/en-US/docs/Web/CSS/grid-row)_
    row: Var[str]

    # Shorthand prop for gridTemplateColumns.
    # Learn more _[here](https://developer.mozilla.org/en-US/docs/Web/CSS/grid-template-columns)_
    template_columns: Var[str]

    # Shorthand prop for gridTemplateRows.
    # Learn more _[here](https://developer.mozilla.org/en-US/docs/Web/CSS/grid-template-rows)_
    template_rows: Var[str]


class GridItem(ChakraComponent):
    """Used as a child of Grid to control the span, and start positions within the grid."""

    tag = "GridItem"

    # Shorthand prop for gridArea
    # Learn more _[here](https://developer.mozilla.org/en-US/docs/Web/CSS/grid-area)_
    area: Var[str]

    # Shorthand prop for gridColumnEnd
    # Learn more _[here](https://developer.mozilla.org/en-US/docs/Web/CSS/grid-column-end)_
    col_end: Var[str]

    # The column number the grid item should start.
    col_start: Var[int]

    # The number of columns the grid item should span.
    col_span: Var[int]

    # Shorthand prop for gridRowEnd
    # Learn more _[here](https://developer.mozilla.org/en-US/docs/Web/CSS/grid-row-end)_
    row_end: Var[str]

    # The row number the grid item should start.
    row_start: Var[int]

    # The number of rows the grid item should span.
    row_span: Var[int]


class ResponsiveGrid(ChakraComponent):
    """A responsive grid component."""

    tag = "SimpleGrid"

    # Shorthand prop for gridAutoColumns to provide automatic column sizing based on content.
    # Learn more _[here](https://developer.mozilla.org/en-US/docs/Web/CSS/grid-auto-columns)_
    auto_columns: Var[str]

    # Shorthand prop for gridAutoFlow to specify exactly how
    # auto-placed items get flowed into the grid.
    # Learn more _[here](https://developer.mozilla.org/en-US/docs/Web/CSS/grid-auto-flow)_
    auto_flow: Var[str]

    # Shorthand prop for gridAutoRows.
    # Learn more _[here](https://developer.mozilla.org/en-US/docs/Web/CSS/grid-auto-rows)_
    auto_rows: Var[str]

    # Shorthand prop for gridColumn.
    # Learn more _[here](https://developer.mozilla.org/en-US/docs/Web/CSS/grid-column)_
    column: Var[str]

    # Shorthand prop for gridRow.
    # Learn more _[here](https://developer.mozilla.org/en-US/docs/Web/CSS/grid-row)_
    row: Var[str]

    # A list that defines the number of columns for each breakpoint.
    columns: Var[List[int]]

    # The width at which child elements will break into columns. Pass a number for pixel values or a string for any other valid CSS length.
    min_child_width: Var[str]

    # The gap between the grid items
    spacing: Var[str]

    # The column gap between the grid items
    spacing_x: Var[str]

    # The row gap between the grid items
    spacing_y: Var[str]

    # Shorthand prop for gridTemplateAreas
    # Learn more _[here](https://developer.mozilla.org/en-US/docs/Web/CSS/grid-template-areas)_
    template_areas: Var[str]

    # Shorthand prop for gridTemplateColumns.
    # Learn more _[here](https://developer.mozilla.org/en-US/docs/Web/CSS/grid-template-columns)_
    template_columns: Var[str]

    # Shorthand prop for gridTemplateRows.
    # Learn more _[here](https://developer.mozilla.org/en-US/docs/Web/CSS/grid-template-rows)_
    template_rows: Var[str]
