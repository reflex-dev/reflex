"""Element classes. This is an auto-generated file. Do not edit. See ../generate.py."""
from typing import Union

from reflex.vars import Var as Var_

from .base import BaseHTML


class Caption(BaseHTML):
    """Display the caption element."""

    tag = "caption"
    align: Var_[Union[str, int, bool]]


class Col(BaseHTML):
    """Display the col element."""

    tag = "col"
    align: Var_[Union[str, int, bool]]
    bgcolor: Var_[Union[str, int, bool]]
    span: Var_[Union[str, int, bool]]


class Colgroup(BaseHTML):
    """Display the colgroup element."""

    tag = "colgroup"
    align: Var_[Union[str, int, bool]]
    bgcolor: Var_[Union[str, int, bool]]
    span: Var_[Union[str, int, bool]]


class Table(BaseHTML):
    """Display the table element."""

    tag = "table"
    align: Var_[Union[str, int, bool]]
    background: Var_[Union[str, int, bool]]
    bgcolor: Var_[Union[str, int, bool]]
    border: Var_[Union[str, int, bool]]
    summary: Var_[Union[str, int, bool]]


class Tbody(BaseHTML):
    """Display the tbody element."""

    tag = "tbody"
    align: Var_[Union[str, int, bool]]
    bgcolor: Var_[Union[str, int, bool]]


class Td(BaseHTML):
    """Display the td element."""

    tag = "td"
    align: Var_[Union[str, int, bool]]
    background: Var_[Union[str, int, bool]]
    bgcolor: Var_[Union[str, int, bool]]
    col_span: Var_[Union[str, int, bool]]
    headers: Var_[Union[str, int, bool]]
    row_span: Var_[Union[str, int, bool]]


class Tfoot(BaseHTML):
    """Display the tfoot element."""

    tag = "tfoot"
    align: Var_[Union[str, int, bool]]
    bgcolor: Var_[Union[str, int, bool]]


class Th(BaseHTML):
    """Display the th element."""

    tag = "th"
    align: Var_[Union[str, int, bool]]
    background: Var_[Union[str, int, bool]]
    bgcolor: Var_[Union[str, int, bool]]
    col_span: Var_[Union[str, int, bool]]
    headers: Var_[Union[str, int, bool]]
    row_span: Var_[Union[str, int, bool]]
    scope: Var_[Union[str, int, bool]]


class Thead(BaseHTML):
    """Display the thead element."""

    tag = "thead"
    align: Var_[Union[str, int, bool]]


class Tr(BaseHTML):
    """Display the tr element."""

    tag = "tr"
    align: Var_[Union[str, int, bool]]
    bgcolor: Var_[Union[str, int, bool]]
