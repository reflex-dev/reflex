"""Element classes. This is an auto-generated file. Do not edit. See ../generate.py."""
from typing import Union

from reflex.vars import Var as Var

from .base import BaseHTML


class Blockquote(BaseHTML):
    """Display the blockquote element."""

    tag = "blockquote"

    # Define the title of a work.
    cite: Var[Union[str, int, bool]]


class Dd(BaseHTML):
    """Display the dd element."""

    tag = "dd"


class Div(BaseHTML):
    """Display the div element."""

    tag = "div"


class Dl(BaseHTML):
    """Display the dl element."""

    tag = "dl"


class Dt(BaseHTML):
    """Display the dt element."""

    tag = "dt"


class Figcaption(BaseHTML):
    """Display the figcaption element."""

    tag = "figcaption"


class Hr(BaseHTML):
    """Display the hr element."""

    tag = "hr"

    # Used to specify the alignment of text content of The Element. this attribute is used in all elements.
    align: Var[Union[str, int, bool]]


class Li(BaseHTML):
    """Display the li element."""

    tag = "li"


class Menu(BaseHTML):
    """Display the menu element."""

    tag = "menu"

    # Specifies that the menu element is a context menu.
    type: Var[Union[str, int, bool]]


class Ol(BaseHTML):
    """Display the ol element."""

    tag = "ol"

    # Reverses the order of the list.
    reversed: Var[Union[str, int, bool]]

    # Specifies the start value of the first list item in an ordered list.
    start: Var[Union[str, int, bool]]

    # Specifies the kind of marker to use in the list (letters or numbers).
    type: Var[Union[str, int, bool]]


class P(BaseHTML):
    """Display the p element."""

    tag = "p"


class Pre(BaseHTML):
    """Display the pre element."""

    tag = "pre"


class Ul(BaseHTML):
    """Display the ul element."""

    tag = "ul"


class Ins(BaseHTML):
    """Display the ins element."""

    tag = "ins"

    # Specifies the URL of the document that explains the reason why the text was inserted/changed.
    cite: Var[Union[str, int, bool]]

    # Specifies the date and time of when the text was inserted/changed.
    date_time: Var[Union[str, int, bool]]


class Del(BaseHTML):
    """Display the del element."""

    tag = "del"

    # Specifies the URL of the document that explains the reason why the text was deleted.
    cite: Var[Union[str, int, bool]]

    # Specifies the date and time of when the text was deleted.
    date_time: Var[Union[str, int, bool]]


blockquote = Blockquote.create
dd = Dd.create
div = Div.create
dl = Dl.create
dt = Dt.create
figcaption = Figcaption.create
hr = Hr.create
li = Li.create
ol = Ol.create
p = P.create
pre = Pre.create
ul = Ul.create
ins = Ins.create
del_ = Del.create  # 'del' is a reserved keyword in Python
