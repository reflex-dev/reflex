"""Element classes. This is an auto-generated file. Do not edit. See ../generate.py."""
from typing import Union

from reflex.vars import Var as Var

from .base import BaseHTML


class Blockquote(BaseHTML):
    """Display the blockquote element."""

    tag: str = "blockquote"

    # Define the title of a work.
    cite: Var[Union[str, int, bool]]


class Dd(BaseHTML):
    """Display the dd element."""

    tag: str = "dd"


class Div(BaseHTML):
    """Display the div element."""

    tag: str = "div"


class Dl(BaseHTML):
    """Display the dl element."""

    tag: str = "dl"


class Dt(BaseHTML):
    """Display the dt element."""

    tag: str = "dt"


class Figcaption(BaseHTML):
    """Display the figcaption element."""

    tag: str = "figcaption"


class Hr(BaseHTML):
    """Display the hr element."""

    tag: str = "hr"

    # Used to specify the alignment of text content of The Element. this attribute is used in all elements.
    align: Var[Union[str, int, bool]]

    # Used to specify the color of a Horizontal rule.
    color: Var[Union[str, int, bool]]


class Li(BaseHTML):
    """Display the li element."""

    tag: str = "li"


class Menu(BaseHTML):
    """Display the menu element."""

    tag: str = "menu"

    # Specifies that the menu element is a context menu.
    type: Var[Union[str, int, bool]]


class Ol(BaseHTML):
    """Display the ol element."""

    tag: str = "ol"

    # Reverses the order of the list.
    reversed: Var[Union[str, int, bool]]

    # Specifies the start value of the first list item in an ordered list.
    start: Var[Union[str, int, bool]]

    # Specifies the kind of marker to use in the list (letters or numbers).
    type: Var[Union[str, int, bool]]


class P(BaseHTML):
    """Display the p element."""

    tag: str = "p"


class Pre(BaseHTML):
    """Display the pre element."""

    tag: str = "pre"


class Ul(BaseHTML):
    """Display the ul element."""

    tag: str = "ul"


class Ins(BaseHTML):
    """Display the ins element."""

    tag: str = "ins"

    # Specifies the URL of the document that explains the reason why the text was inserted/changed.
    cite: Var[Union[str, int, bool]]

    # Specifies the date and time of when the text was inserted/changed.
    date_time: Var[Union[str, int, bool]]


class Del(BaseHTML):
    """Display the del element."""

    tag: str = "del"

    # Specifies the URL of the document that explains the reason why the text was deleted.
    cite: Var[Union[str, int, bool]]

    # Specifies the date and time of when the text was deleted.
    date_time: Var[Union[str, int, bool]]
