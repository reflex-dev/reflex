"""Interactive components provided by @radix-ui/themes."""

from typing import Literal

from reflex_base.components.component import field
from reflex_base.vars.base import Var
from reflex_components_core.core.breakpoints import Responsive
from reflex_components_core.el import elements

from reflex_components_radix.themes.base import RadixThemesComponent

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
