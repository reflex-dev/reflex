"""Typography classes."""

from typing import Literal

from reflex.vars.base import Var

from .base import BaseHTML


class Blockquote(BaseHTML):
    """Display the blockquote element."""

    tag = "blockquote"

    # Define the title of a work.
    cite: Var[str]


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


class Li(BaseHTML):
    """Display the li element."""

    tag = "li"


class Menu(BaseHTML):
    """Display the menu element."""

    tag = "menu"

    # Specifies that the menu element is a context menu.
    type: Var[str]


class Ol(BaseHTML):
    """Display the ol element."""

    tag = "ol"

    # Reverses the order of the list.
    reversed: Var[bool]

    # Specifies the start value of the first list item in an ordered list.
    start: Var[int]

    # Specifies the kind of marker to use in the list (letters or numbers).
    type: Var[Literal["1", "a", "A", "i", "I"]]


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
    cite: Var[str]

    # Specifies the date and time of when the text was inserted/changed.
    date_time: Var[str]


class Del(BaseHTML):
    """Display the del element."""

    tag = "del"

    # Specifies the URL of the document that explains the reason why the text was deleted.
    cite: Var[str]

    # Specifies the date and time of when the text was deleted.
    date_time: Var[str]


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
