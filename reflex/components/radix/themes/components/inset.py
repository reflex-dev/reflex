"""Interactive components provided by @radix-ui/themes."""

from typing import Literal

from reflex.components.core.breakpoints import Responsive
from reflex.components.el import elements
from reflex.vars.base import Var

from ..base import RadixThemesComponent

LiteralButtonSize = Literal["1", "2", "3", "4"]


class Inset(elements.Div, RadixThemesComponent):
    """Applies a negative margin to allow content to bleed into the surrounding container."""

    tag = "Inset"

    # The side
    side: Var[Responsive[Literal["x", "y", "top", "bottom", "right", "left"]]]

    # How to clip the element's content: "border-box" | "padding-box"
    clip: Var[Responsive[Literal["border-box", "padding-box"]]]

    # Padding
    p: Var[Responsive[int | str]]

    # Padding on the x axis
    px: Var[Responsive[int | str]]

    # Padding on the y axis
    py: Var[Responsive[int | str]]

    # Padding on the top
    pt: Var[Responsive[int | str]]

    # Padding on the right
    pr: Var[Responsive[int | str]]

    # Padding on the bottom
    pb: Var[Responsive[int | str]]

    # Padding on the left
    pl: Var[Responsive[int | str]]


inset = Inset.create
