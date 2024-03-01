"""Element classes. This is an auto-generated file. Do not edit. See ../generate.py."""
from typing import Optional, Union

from reflex.vars import Var as Var

from .base import BaseHTML


class Caption(BaseHTML):
    """Display the caption element."""

    tag: str = "caption"

    # Alignment of the caption
    align: Optional[Var[Union[str, int, bool]]] = None


class Col(BaseHTML):
    """Display the col element."""

    tag: str = "col"

    # Alignment of the content within the column
    align: Optional[Var[Union[str, int, bool]]] = None

    # Number of columns the col element spans
    span: Optional[Var[Union[str, int, bool]]] = None


class Colgroup(BaseHTML):
    """Display the colgroup element."""

    tag: str = "colgroup"

    # Alignment of the content within the column group
    align: Optional[Var[Union[str, int, bool]]] = None

    # Number of columns the colgroup element spans
    span: Optional[Var[Union[str, int, bool]]] = None


class Table(BaseHTML):
    """Display the table element."""

    tag: str = "table"

    # Alignment of the table
    align: Optional[Var[Union[str, int, bool]]] = None

    # Provides a summary of the table's purpose and structure
    summary: Optional[Var[Union[str, int, bool]]] = None


class Tbody(BaseHTML):
    """Display the tbody element."""

    tag: str = "tbody"

    # Alignment of the content within the table body
    align: Optional[Var[Union[str, int, bool]]] = None


class Td(BaseHTML):
    """Display the td element."""

    tag: str = "td"

    # Alignment of the content within the table cell
    align: Optional[Var[Union[str, int, bool]]] = None

    # Number of columns a cell should span
    col_span: Optional[Var[Union[str, int, bool]]] = None

    # IDs of the headers associated with this cell
    headers: Optional[Var[Union[str, int, bool]]] = None

    # Number of rows a cell should span
    row_span: Optional[Var[Union[str, int, bool]]] = None


class Tfoot(BaseHTML):
    """Display the tfoot element."""

    tag: str = "tfoot"

    # Alignment of the content within the table footer
    align: Optional[Var[Union[str, int, bool]]] = None


class Th(BaseHTML):
    """Display the th element."""

    tag: str = "th"

    # Alignment of the content within the table header cell
    align: Optional[Var[Union[str, int, bool]]] = None

    # Number of columns a header cell should span
    col_span: Optional[Var[Union[str, int, bool]]] = None

    # IDs of the headers associated with this header cell
    headers: Optional[Var[Union[str, int, bool]]] = None

    # Number of rows a header cell should span
    row_span: Optional[Var[Union[str, int, bool]]] = None

    # Scope of the header cell (row, col, rowgroup, colgroup)
    scope: Optional[Var[Union[str, int, bool]]] = None


class Thead(BaseHTML):
    """Display the thead element."""

    tag: str = "thead"

    # Alignment of the content within the table header
    align: Optional[Var[Union[str, int, bool]]] = None


class Tr(BaseHTML):
    """Display the tr element."""

    tag: str = "tr"

    # Alignment of the content within the table row
    align: Optional[Var[Union[str, int, bool]]] = None
