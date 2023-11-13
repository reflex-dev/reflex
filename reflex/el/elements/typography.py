"""Element classes. This is an auto-generated file. Do not edit. See ../generate.py."""
from typing import Union

from reflex.el.element import Element
from reflex.vars import Var as Var_
from .base import BaseHTML

class Blockquote(BaseHTML):  # noqa: E742
    """Display the blockquote element."""

    tag = "blockquote"

    cite: Var_[Union[str, int, bool]]


class Dd(BaseHTML):  # noqa: E742
    """Display the dd element."""

    tag = "dd"


class Div(BaseHTML):  # noqa: E742
    """Display the div element."""

    tag = "div"


class Dl(BaseHTML):  # noqa: E742
    """Display the dl element."""

    tag = "dl"


class Dt(BaseHTML):  # noqa: E742
    """Display the dt element."""

    tag = "dt"


class Figcaption(BaseHTML):  # noqa: E742
    """Display the figcaption element."""

    tag = "figcaption"


class Hr(BaseHTML):  # noqa: E742
    """Display the hr element."""

    tag = "hr"

    align: Var_[Union[str, int, bool]]
    color: Var_[Union[str, int, bool]]


class Li(BaseHTML):  # noqa: E742
    """Display the li element."""

    tag = "li"


class Menu(BaseHTML):  # noqa: E742
    """Display the menu element."""

    tag = "menu"

    type: Var_[Union[str, int, bool]]


class Ol(BaseHTML):  # noqa: E742
    """Display the ol element."""

    tag = "ol"

    reversed: Var_[Union[str, int, bool]]
    start: Var_[Union[str, int, bool]]
    type: Var_[Union[str, int, bool]]


class P(BaseHTML):  # noqa: E742
    """Display the p element."""

    tag = "p"


class Pre(BaseHTML):  # noqa: E742
    """Display the pre element."""

    tag = "pre"


class Ul(BaseHTML):  # noqa: E742
    """Display the ul element."""

    tag = "ul"


class Ins(BaseHTML):
    """Display the ins element."""
    tag = "ins"
    cite: Var_[Union[str, int, bool]]
    date_time: Var_[Union[str, int, bool]]

class Del(BaseHTML):
    """Display the del element."""
    tag = "del"
    cite: Var_[Union[str, int, bool]]
    date_time: Var_[Union[str, int, bool]]