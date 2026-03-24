"""Interactive components provided by @radix-ui/themes."""

from typing import Literal

from reflex.components.component import field
from reflex.components.core.breakpoints import Responsive
from reflex.components.el import elements
from reflex.components.radix.themes.base import RadixThemesComponent
from reflex.vars.base import Var

LiteralButtonSize = Literal["1", "2", "3", "4"]


class Inset(elements.Div, RadixThemesComponent):
    """Applies a negative margin to allow content to bleed into the surrounding container."""

    tag = "Inset"

    side: Var[Responsive[Literal["x", "y", "top", "bottom", "right", "left"]]] = field(
        doc="The side"
    )

    clip: Var[Responsive[Literal["border-box", "padding-box"]]] = field(
        doc='How to clip the element\'s content: "border-box" | "padding-box"'
    )

    p: Var[Responsive[int | str]] = field(doc="Padding")

    px: Var[Responsive[int | str]] = field(doc="Padding on the x axis")

    py: Var[Responsive[int | str]] = field(doc="Padding on the y axis")

    pt: Var[Responsive[int | str]] = field(doc="Padding on the top")

    pr: Var[Responsive[int | str]] = field(doc="Padding on the right")

    pb: Var[Responsive[int | str]] = field(doc="Padding on the bottom")

    pl: Var[Responsive[int | str]] = field(doc="Padding on the left")


inset = Inset.create
