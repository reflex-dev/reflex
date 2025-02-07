"""Tables classes."""

from typing import Literal

from reflex.vars.base import Var

from .base import BaseHTML


class Caption(BaseHTML):
    """Display the caption element."""

    tag = "caption"


class Col(BaseHTML):
    """Display the col element."""

    tag = "col"

    # Number of columns the col element spans
    span: Var[int]


class Colgroup(BaseHTML):
    """Display the colgroup element."""

    tag = "colgroup"

    # Number of columns the colgroup element spans
    span: Var[int]


class Table(BaseHTML):
    """Display the table element."""

    tag = "table"

    # Alignment of the table
    align: Var[Literal["left", "center", "right"]]

    # Provides a summary of the table's purpose and structure
    summary: Var[str]


class Tbody(BaseHTML):
    """Display the tbody element."""

    tag = "tbody"


class Td(BaseHTML):
    """Display the td element."""

    tag = "td"

    # Alignment of the content within the table cell
    align: Var[Literal["left", "center", "right", "justify", "char"]]

    # Number of columns a cell should span
    col_span: Var[int]

    # IDs of the headers associated with this cell
    headers: Var[str]

    # Number of rows a cell should span
    row_span: Var[int]


class Tfoot(BaseHTML):
    """Display the tfoot element."""

    tag = "tfoot"


class Th(BaseHTML):
    """Display the th element."""

    tag = "th"

    # Alignment of the content within the table header cell
    align: Var[Literal["left", "center", "right", "justify", "char"]]

    # Number of columns a header cell should span
    col_span: Var[int]

    # IDs of the headers associated with this header cell
    headers: Var[str]

    # Number of rows a header cell should span
    row_span: Var[int]

    # Scope of the header cell (row, col, rowgroup, colgroup)
    scope: Var[str]


class Thead(BaseHTML):
    """Display the thead element."""

    tag = "thead"


class Tr(BaseHTML):
    """Display the tr element."""

    tag = "tr"


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
