"""Tables classes."""

from typing import Literal

from reflex_base.components.component import field
from reflex_base.vars.base import Var

from .base import BaseHTML


class Caption(BaseHTML):
    """Display the caption element."""

    tag = "caption"


class Col(BaseHTML):
    """Display the col element."""

    tag = "col"

    span: Var[int] = field(doc="Number of columns the col element spans")


class Colgroup(BaseHTML):
    """Display the colgroup element."""

    tag = "colgroup"

    span: Var[int] = field(doc="Number of columns the colgroup element spans")


class Table(BaseHTML):
    """Display the table element."""

    tag = "table"

    align: Var[Literal["left", "center", "right"]] = field(doc="Alignment of the table")

    summary: Var[str] = field(
        doc="Provides a summary of the table's purpose and structure"
    )


class Tbody(BaseHTML):
    """Display the tbody element."""

    tag = "tbody"


class Td(BaseHTML):
    """Display the td element."""

    tag = "td"

    align: Var[Literal["left", "center", "right", "justify", "char"]] = field(
        doc="Alignment of the content within the table cell"
    )

    col_span: Var[int] = field(doc="Number of columns a cell should span")

    headers: Var[str] = field(doc="IDs of the headers associated with this cell")

    row_span: Var[int] = field(doc="Number of rows a cell should span")


class Tfoot(BaseHTML):
    """Display the tfoot element."""

    tag = "tfoot"


class Th(BaseHTML):
    """Display the th element."""

    tag = "th"

    align: Var[Literal["left", "center", "right", "justify", "char"]] = field(
        doc="Alignment of the content within the table header cell"
    )

    col_span: Var[int] = field(doc="Number of columns a header cell should span")

    headers: Var[str] = field(doc="IDs of the headers associated with this header cell")

    row_span: Var[int] = field(doc="Number of rows a header cell should span")

    scope: Var[str] = field(
        doc="Scope of the header cell (row, col, rowgroup, colgroup)"
    )


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
