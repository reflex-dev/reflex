"""Element classes. This is an auto-generated file. Do not edit. See ../generate.py."""
from typing import Union

from reflex.el.element import Element
from reflex.vars import Var as Var_
from .base import BaseHTML


class Details(BaseHTML):
    """Display the details element."""
    tag = "details"
    open: Var_[Union[str, int, bool]]


class Dialog(BaseHTML):
    """Display the dialog element."""
    tag = "dialog"
    open: Var_[Union[str, int, bool]]


class Summary(BaseHTML):  # noqa: E742
    """Display the summary element."""

    tag = "summary"


class Slot(BaseHTML):  # noqa: E742
    """Display the slot element."""

    tag = "slot"


class Template(BaseHTML):  # noqa: E742
    """Display the template element."""

    tag = "template"


class Svg(BaseHTML):  # noqa: E742
    """Display the svg element."""

    tag = "svg"


class Math(BaseHTML):  # noqa: E742
    """Display the math element."""

    tag = "math"


class Html(BaseHTML):
    """Display the html element."""
    tag = "html"
    manifest: Var_[Union[str, int, bool]]