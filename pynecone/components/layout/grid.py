"""Container to stack elements with spacing."""

from typing import List

from pynecone.components.libs.chakra import ChakraComponent
from pynecone.var import Var


class Grid(ChakraComponent):
    """The main wrapper of th egrid component."""

    tag = "Grid"

    # Shorthand prop for gridAutoColumns
    auto_columns: Var[str]

    # Shorthand prop for gridAutoFlow
    auto_flow: Var[str]

    # Shorthand prop for gridAutoRows
    auto_rows: Var[str]

    # Shorthand prop for gridColumn
    column: Var[str]

    # Shorthand prop for gridRow
    row: Var[str]

    # Shorthand prop for gridTemplateColumns
    template_columns: Var[str]

    # Shorthand prop for gridTemplateRows
    template_rows: Var[str]


class GridItem(ChakraComponent):
    """Used as a child of Grid to control the span, and start positions within the grid."""

    tag = "GridItem"

    # Shorthand prop for gridArea
    area: Var[str]

    # Shorthand prop for gridColumnEnd
    col_end: Var[str]

    # The column number the grid item should start.
    col_start: Var[int]

    # The number of columns the grid item should span.
    col_span: Var[int]

    # Shorthand prop for gridRowEnd
    row_end: Var[str]

    # The row number the grid item should start.
    row_start: Var[int]

    # The number of rows the grid item should span.
    row_span: Var[int]


class ResponsiveGrid(ChakraComponent):
    """A responsive grid component."""

    tag = "SimpleGrid"

    # Shorthand prop for gridAutoColumns
    auto_columns: Var[str]

    # Shorthand prop for gridAutoFlow
    auto_flow: Var[str]

    # Shorthand prop for gridAutoRows
    auto_rows: Var[str]

    # Shorthand prop for gridColumn
    column: Var[str]

    # Shorthand prop for gridRow
    row: Var[str]

    # Alist that defines the number of columns for each breakpoint.
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
    template_areas: Var[str]

    # Shorthand prop for gridTemplateColumns
    template_columns: Var[str]

    # Shorthand prop for gridTemplateRows
    template_rows: Var[str]
