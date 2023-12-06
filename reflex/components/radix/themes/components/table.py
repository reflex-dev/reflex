"""Interactive components provided by @radix-ui/themes."""
from typing import Literal, Union

from reflex import el
from reflex.vars import Var

from ..base import (
    CommonMarginProps,
    RadixThemesComponent,
)


class TableRoot(el.Table, CommonMarginProps, RadixThemesComponent):
    """Trigger an action or event, such as submitting a form or displaying a dialog."""

    tag = "Table.Root"

    # The size of the table: "1" | "2" | "3"
    size: Var[Literal[1, 2, 3]]

    # The variant of the table
    variant: Var[Literal["surface", "ghost"]]


class TableHeader(el.Thead, CommonMarginProps, RadixThemesComponent):
    """Trigger an action or event, such as submitting a form or displaying a dialog."""

    tag = "Table.Header"


class TableRow(el.Tr, CommonMarginProps, RadixThemesComponent):
    """Trigger an action or event, such as submitting a form or displaying a dialog."""

    tag = "Table.Row"

    # The alignment of the row
    align: Var[Literal["start", "center", "end", "baseline"]]


class TableColumnHeaderCell(el.Th, CommonMarginProps, RadixThemesComponent):
    """Trigger an action or event, such as submitting a form or displaying a dialog."""

    tag = "Table.ColumnHeaderCell"

    # The justification of the column
    justify: Var[Literal["start", "center", "end"]]

    # width of the column
    width: Var[Union[str, int]]


class TableBody(el.Tbody, CommonMarginProps, RadixThemesComponent):
    """Trigger an action or event, such as submitting a form or displaying a dialog."""

    tag = "Table.Body"


class TableCell(el.Td, CommonMarginProps, RadixThemesComponent):
    """Trigger an action or event, such as submitting a form or displaying a dialog."""

    tag = "Table.Cell"

    # The justification of the column
    justify: Var[Literal["start", "center", "end"]]

    # width of the column
    width: Var[Union[str, int]]


class TableRowHeaderCell(el.Th, CommonMarginProps, RadixThemesComponent):
    """Trigger an action or event, such as submitting a form or displaying a dialog."""

    tag = "Table.RowHeaderCell"

    # The justification of the column
    justify: Var[Literal["start", "center", "end"]]

    # width of the column
    width: Var[Union[str, int]]
