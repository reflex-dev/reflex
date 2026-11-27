"""A table: rows of cells under a header."""

from __future__ import annotations

from typing import ClassVar, Literal

from reflex_base.components.component import Component, ComponentNamespace, field
from reflex_base.vars.base import Var
from reflex_components_core.core.breakpoints import Responsive
from reflex_components_core.el import elements

from reflex_components_ui.base import Part, UIComponent
from reflex_components_ui.props import LiteralSpacing, style_props
from reflex_components_ui.style import ComponentStyles
from reflex_components_ui.styles.table import (
    TABLE_BODY,
    TABLE_CELL,
    TABLE_COLUMN_HEADER_CELL,
    TABLE_HEADER,
    TABLE_ROOT,
    TABLE_ROW,
    TABLE_ROW_HEADER_CELL,
)

# The props of a cell that are the CSS property of the same name.
_WIDTH_PROPS = ("min_width", "max_width")


class TableRootTable(Part):
    """The table inside a table root, which the header and the body go in."""

    tag = "table"


class TableRoot(UIComponent, elements.Table):
    """A semantic table for presenting tabular data."""

    tag = "div"

    styles: ClassVar[ComponentStyles] = TABLE_ROOT

    size: Var[Responsive[Literal["1", "2", "3"]]] = field(
        doc='The size of the table: "1" | "2" | "3"'
    )

    variant: Var[Literal["surface", "ghost"]] = field(doc="The variant of the table")

    @classmethod
    def create(cls, *children, **props) -> Component:
        """Create a table, inside a box that scrolls when it is too wide.

        Args:
            *children: The header and the body of the table.
            **props: The props of the table.

        Returns:
            The root: a block around the box that scrolls, around the table.
        """
        return super().create(
            Part.create(
                Part.create(
                    TableRootTable.create(*children, part="table"),
                    part="content",
                    tag="div",
                ),
                part="scroll",
                tag="div",
            ),
            **props,
        )


class TableHeader(UIComponent, elements.Thead):
    """The header of the table defines column names and other non-data elements."""

    tag = "thead"

    styles: ClassVar[ComponentStyles] = TABLE_HEADER

    _invalid_children: ClassVar[list[str]] = ["TableBody"]

    _valid_parents: ClassVar[list[str]] = ["TableRootTable"]


class TableRow(UIComponent, elements.Tr):
    """A row containing table cells."""

    tag = "tr"

    styles: ClassVar[ComponentStyles] = TABLE_ROW

    align: Var[Literal["start", "center", "end", "baseline"]] = field(
        doc="The alignment of the row"
    )

    _invalid_children: ClassVar[list[str]] = ["TableBody", "TableHeader", "TableRow"]


class TableBody(UIComponent, elements.Tbody):
    """The body of the table contains the data rows."""

    tag = "tbody"

    styles: ClassVar[ComponentStyles] = TABLE_BODY

    _invalid_children: ClassVar[list[str]] = [
        "TableHeader",
        "TableRowHeaderCell",
        "TableColumnHeaderCell",
        "TableCell",
    ]

    _valid_parents: ClassVar[list[str]] = ["TableRootTable"]


class BaseCell(UIComponent):
    """What every cell of a table shares."""

    justify: Var[Literal["start", "center", "end"]] = field(
        doc="The justification of the column"
    )

    min_width: Var[Responsive[str]] = field(doc="The minimum width of the cell")

    max_width: Var[Responsive[str]] = field(doc="The maximum width of the cell")

    @classmethod
    def create(cls, *children, **props) -> Component:
        """Create a cell, its width props as styles.

        Args:
            *children: The children of the cell.
            **props: The props of the cell.

        Returns:
            The cell.
        """
        style_props("rx.ui.table cell", props, _WIDTH_PROPS)
        return super().create(*children, **props)


class PaddingProps(UIComponent):
    """The padding props of a cell, in steps of the space scale."""

    p: Var[Responsive[LiteralSpacing]] = field(doc='Padding: "0" - "9" # noqa: ERA001')

    px: Var[Responsive[LiteralSpacing]] = field(doc='Padding horizontal: "0" - "9"')

    py: Var[Responsive[LiteralSpacing]] = field(doc='Padding vertical: "0" - "9"')

    pt: Var[Responsive[LiteralSpacing]] = field(doc='Padding top: "0" - "9"')

    pr: Var[Responsive[LiteralSpacing]] = field(doc='Padding right: "0" - "9"')

    pb: Var[Responsive[LiteralSpacing]] = field(doc='Padding bottom: "0" - "9"')

    pl: Var[Responsive[LiteralSpacing]] = field(doc='Padding left: "0" - "9"')


class TableColumnHeaderCell(BaseCell, elements.Th):
    """A table cell that is semantically treated as a column header."""

    tag = "th"

    styles: ClassVar[ComponentStyles] = TABLE_COLUMN_HEADER_CELL

    _invalid_children: ClassVar[list[str]] = [
        "TableBody",
        "TableHeader",
        "TableRow",
        "TableCell",
        "TableColumnHeaderCell",
        "TableRowHeaderCell",
    ]


class TableCell(BaseCell, PaddingProps, elements.Td):
    """A cell containing data."""

    tag = "td"

    styles: ClassVar[ComponentStyles] = TABLE_CELL

    _invalid_children: ClassVar[list[str]] = [
        "TableBody",
        "TableHeader",
        "TableRowHeaderCell",
        "TableColumnHeaderCell",
        "TableCell",
    ]


class TableRowHeaderCell(BaseCell, PaddingProps, elements.Th):
    """A table cell that is semantically treated as a row header."""

    tag = "th"

    styles: ClassVar[ComponentStyles] = TABLE_ROW_HEADER_CELL

    _invalid_children: ClassVar[list[str]] = [
        "TableBody",
        "TableHeader",
        "TableRow",
        "TableCell",
        "TableColumnHeaderCell",
        "TableRowHeaderCell",
    ]


class Table(ComponentNamespace):
    """Table components namespace."""

    root = staticmethod(TableRoot.create)
    header = staticmethod(TableHeader.create)
    body = staticmethod(TableBody.create)
    row = staticmethod(TableRow.create)
    cell = staticmethod(TableCell.create)
    column_header_cell = staticmethod(TableColumnHeaderCell.create)
    row_header_cell = staticmethod(TableRowHeaderCell.create)


table = Table()
