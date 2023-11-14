"""Element classes. This is an auto-generated file. Do not edit. See ../generate.py."""
from typing import Union

from reflex.vars import Var as Var_

from .base import BaseHTML


class Blockquote(BaseHTML):  # noqa: E742
    """Display the blockquote element."""

    tag = "blockquote"

    # Define the title of a work.
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

    # Used to specify the alignment of text content of The Element. this attribute is used in all elements.
    align: Var_[Union[str, int, bool]]

    # Used to specify the color of a Horizontal rule.
    color: Var_[Union[str, int, bool]]


class Li(BaseHTML):  # noqa: E742
    """Display the li element."""

    tag = "li"


class Menu(BaseHTML):  # noqa: E742
    """Display the menu element."""

    tag = "menu"

    # Specifies that the menu element is a context menu.
    type: Var_[Union[str, int, bool]]


class Ol(BaseHTML):  # noqa: E742
    """Display the ol element."""

    tag = "ol"

    # Reverses the order of the list.
    reversed: Var_[Union[str, int, bool]]

    # Specifies the start value of the first list item in an ordered list.
    start: Var_[Union[str, int, bool]]

    # Specifies the kind of marker to use in the list (letters or numbers).
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

    # Specifies the URL of the document that explains the reason why the text was inserted/changed.
    cite: Var_[Union[str, int, bool]]

    # Specifies the date and time of when the text was inserted/changed.
    date_time: Var_[Union[str, int, bool]]


class Del(BaseHTML):
    """Display the del element."""

    tag = "del"

    # Specifies the URL of the document that explains the reason why the text was deleted.
    cite: Var_[Union[str, int, bool]]

    # Specifies the date and time of when the text was deleted.
    date_time: Var_[Union[str, int, bool]]
