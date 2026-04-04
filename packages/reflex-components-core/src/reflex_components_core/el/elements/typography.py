"""Typography classes."""

from typing import ClassVar, Literal

from reflex_base.components.component import field
from reflex_base.vars.base import Var

from .base import BaseHTML


class Blockquote(BaseHTML):
    """Display the blockquote element."""

    tag = "blockquote"

    cite: Var[str] = field(doc="Define the title of a work.")


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


class Figure(BaseHTML):
    """Display the figure element."""

    tag = "figure"


class Hr(BaseHTML):
    """Display the hr element."""

    tag = "hr"


class Li(BaseHTML):
    """Display the li element."""

    tag = "li"


class Menu(BaseHTML):
    """Display the menu element."""

    tag = "menu"

    type: Var[str] = field(doc="Specifies that the menu element is a context menu.")


class Ol(BaseHTML):
    """Display the ol element."""

    tag = "ol"

    reversed: Var[bool] = field(doc="Reverses the order of the list.")

    start: Var[int] = field(
        doc="Specifies the start value of the first list item in an ordered list."
    )

    type: Var[Literal["1", "a", "A", "i", "I"]] = field(
        doc="Specifies the kind of marker to use in the list (letters or numbers)."
    )


class P(BaseHTML):
    """Display the p element."""

    tag = "p"

    _invalid_children: ClassVar[list] = ["P", "Ol", "Ul", "Div"]


class Pre(BaseHTML):
    """Display the pre element."""

    tag = "pre"


class Ul(BaseHTML):
    """Display the ul element."""

    tag = "ul"


class Ins(BaseHTML):
    """Display the ins element."""

    tag = "ins"

    cite: Var[str] = field(
        doc="Specifies the URL of the document that explains the reason why the text was inserted/changed."
    )

    date_time: Var[str] = field(
        doc="Specifies the date and time of when the text was inserted/changed."
    )


class Del(BaseHTML):
    """Display the del element."""

    tag = "del"

    cite: Var[str] = field(
        doc="Specifies the URL of the document that explains the reason why the text was deleted."
    )

    date_time: Var[str] = field(
        doc="Specifies the date and time of when the text was deleted."
    )


blockquote = Blockquote.create
dd = Dd.create
div = Div.create
dl = Dl.create
dt = Dt.create
figcaption = Figcaption.create
figure = Figure.create
hr = Hr.create
li = Li.create
ol = Ol.create
p = P.create
pre = Pre.create
ul = Ul.create
ins = Ins.create
del_ = Del.create  # 'del' is a reserved keyword in Python
