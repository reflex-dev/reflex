"""Element classes. This is an auto-generated file. Do not edit. See ../generate.py."""

from typing import Union

from reflex.vars import Var as Var

from .base import BaseHTML


class Caption(BaseHTML):
    """Display the caption element."""

    tag = "caption"

    # Alignment of the caption
    align: Var[Union[str, int, bool]]


class Col(BaseHTML):
    """Display the col element."""

    tag = "col"

    # Alignment of the content within the column
    align: Var[Union[str, int, bool]]

    # Number of columns the col element spans
    span: Var[Union[str, int, bool]]


class Colgroup(BaseHTML):
    """Display the colgroup element."""

    tag = "colgroup"

    # Alignment of the content within the column group
    align: Var[Union[str, int, bool]]

    # Number of columns the colgroup element spans
    span: Var[Union[str, int, bool]]


class Table(BaseHTML):
    """Display the table element."""

    tag = "table"

    # Alignment of the table
    align: Var[Union[str, int, bool]]

    # Provides a summary of the table's purpose and structure
    summary: Var[Union[str, int, bool]]


class Tbody(BaseHTML):
    """Display the tbody element."""

    tag = "tbody"

    # Alignment of the content within the table body
    align: Var[Union[str, int, bool]]


class Td(BaseHTML):
    """Display the td element."""

    tag = "td"

    # Alignment of the content within the table cell
    align: Var[Union[str, int, bool]]

    # Number of columns a cell should span
    col_span: Var[Union[str, int, bool]]

    # IDs of the headers associated with this cell
    headers: Var[Union[str, int, bool]]

    # Number of rows a cell should span
    row_span: Var[Union[str, int, bool]]


class Tfoot(BaseHTML):
    """Display the tfoot element."""

    tag = "tfoot"

    # Alignment of the content within the table footer
    align: Var[Union[str, int, bool]]


class Th(BaseHTML):
    """Display the th element."""

    tag = "th"

    # Alignment of the content within the table header cell
    align: Var[Union[str, int, bool]]

    # Number of columns a header cell should span
    col_span: Var[Union[str, int, bool]]

    # IDs of the headers associated with this header cell
    headers: Var[Union[str, int, bool]]

    # Number of rows a header cell should span
    row_span: Var[Union[str, int, bool]]

    # Scope of the header cell (row, col, rowgroup, colgroup)
    scope: Var[Union[str, int, bool]]


class Thead(BaseHTML):
    """Display the thead element."""

    tag = "thead"

    # Alignment of the content within the table header
    align: Var[Union[str, int, bool]]


class Tr(BaseHTML):
    """Display the tr element."""

    tag = "tr"

    # Alignment of the content within the table row
    align: Var[Union[str, int, bool]]


caption = Caption.create
col = Col.create
colgroup = Colgroup.create
table = Table.create
tbody = Tbody.create
td = Td.create
tfoot = Tfoot.create
th = Th.create
thead = Thead.create
tr = Tr.create
