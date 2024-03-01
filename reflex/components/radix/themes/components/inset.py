"""Interactive components provided by @radix-ui/themes."""
from typing import Literal, Optional, Union

from reflex import el
from reflex.vars import Var

from ..base import (
    RadixThemesComponent,
)

LiteralButtonSize = Literal["1", "2", "3", "4"]


class Inset(el.Div, RadixThemesComponent):
    """Applies a negative margin to allow content to bleed into the surrounding container."""

    tag: str = "Inset"

    # The side
    side: Optional[Var[Literal["x", "y", "top", "bottom", "right", "left"]]] = None

    # How to clip the element's content: "border-box" | "padding-box"
    clip: Optional[Var[Literal["border-box", "padding-box"]]] = None

    # Padding
    p: Optional[Var[Union[int, str]]] = None

    # Padding on the x axis
    px: Optional[Var[Union[int, str]]] = None

    # Padding on the y axis
    py: Optional[Var[Union[int, str]]] = None

    # Padding on the top
    pt: Optional[Var[Union[int, str]]] = None

    # Padding on the right
    pr: Optional[Var[Union[int, str]]] = None

    # Padding on the bottom
    pb: Optional[Var[Union[int, str]]] = None

    # Padding on the left
    pl: Optional[Var[Union[int, str]]] = None


inset = Inset.create
