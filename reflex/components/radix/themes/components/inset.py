"""Interactive components provided by @radix-ui/themes."""

from typing import Literal, Union

from reflex.components.core.breakpoints import Responsive
from reflex.components.el import elements
from reflex.ivars.base import ImmutableVar

from ..base import (
    RadixThemesComponent,
)

LiteralButtonSize = Literal["1", "2", "3", "4"]


class Inset(elements.Div, RadixThemesComponent):
    """Applies a negative margin to allow content to bleed into the surrounding container."""

    tag = "Inset"

    # The side
    side: ImmutableVar[Responsive[Literal["x", "y", "top", "bottom", "right", "left"]]]

    # How to clip the element's content: "border-box" | "padding-box"
    clip: ImmutableVar[Responsive[Literal["border-box", "padding-box"]]]

    # Padding
    p: ImmutableVar[Responsive[Union[int, str]]]

    # Padding on the x axis
    px: ImmutableVar[Responsive[Union[int, str]]]

    # Padding on the y axis
    py: ImmutableVar[Responsive[Union[int, str]]]

    # Padding on the top
    pt: ImmutableVar[Responsive[Union[int, str]]]

    # Padding on the right
    pr: ImmutableVar[Responsive[Union[int, str]]]

    # Padding on the bottom
    pb: ImmutableVar[Responsive[Union[int, str]]]

    # Padding on the left
    pl: ImmutableVar[Responsive[Union[int, str]]]


inset = Inset.create
