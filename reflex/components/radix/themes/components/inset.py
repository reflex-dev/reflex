"""Interactive components provided by @radix-ui/themes."""
from typing import Literal, Union

from reflex import el
from reflex.vars import Var

from ..base import (
    RadixThemesComponent,
)

LiteralButtonSize = Literal["1", "2", "3", "4"]


class Inset(el.Div, RadixThemesComponent):
    """Applies a negative margin to allow content to bleed into the surrounding container."""

    tag = "Inset"

    # The side
    side: Var[Literal["x", "y", "top", "bottom", "right", "left"]]

    # How to clip the element's content: "border-box" | "padding-box"
    clip: Var[Literal["border-box", "padding-box"]]

    # Padding
    p: Var[Union[int, str]]

    # Padding on the x axis
    px: Var[Union[int, str]]

    # Padding on the y axis
    py: Var[Union[int, str]]

    # Padding on the top
    pt: Var[Union[int, str]]

    # Padding on the right
    pr: Var[Union[int, str]]

    # Padding on the bottom
    pb: Var[Union[int, str]]

    # Padding on the left
    pl: Var[Union[int, str]]


inset = Inset.create
