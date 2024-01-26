"""Interactive components provided by @radix-ui/themes."""
from typing import Literal, Union

from reflex import el
from reflex.vars import Var

from ..base import (
    RadixThemesComponent,
)


class TableRoot(el.Table, RadixThemesComponent):
    """A semantic table for presenting tabular data."""

    tag = "Table.Root"

    # The size of the table: "1" | "2" | "3"
    size: Var[Literal["1", "2", "3"]]

    # The variant of the table
    variant: Var[Literal["surface", "ghost"]]


class TableHeader(el.Thead, RadixThemesComponent):
    """The header of the table defines column names and other non-data elements."""

    tag = "Table.Header"


class TableRow(el.Tr, RadixThemesComponent):
    """A row containing table cells."""

    tag = "Table.Row"

    # The alignment of the row
    align: Var[Literal["start", "center", "end", "baseline"]]


class TableColumnHeaderCell(el.Th, RadixThemesComponent):
    """A table cell that is semantically treated as a column header."""

    tag = "Table.ColumnHeaderCell"

    # The justification of the column
    justify: Var[Literal["start", "center", "end"]]

    # width of the column
    width: Var[Union[str, int]]


class TableBody(el.Tbody, RadixThemesComponent):
    """The body of the table contains the data rows."""

    tag = "Table.Body"


class TableCell(el.Td, RadixThemesComponent):
    """A cell containing data."""

    tag = "Table.Cell"

    # The justification of the column
    justify: Var[Literal["start", "center", "end"]]

    # width of the column
    width: Var[Union[str, int]]


class TableRowHeaderCell(el.Th, RadixThemesComponent):
    """A table cell that is semantically treated as a row header."""

    tag = "Table.RowHeaderCell"

    # The justification of the column
    justify: Var[Literal["start", "center", "end"]]

    # width of the column
    width: Var[Union[str, int]]
