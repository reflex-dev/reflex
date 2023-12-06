"""Interactive components provided by @radix-ui/themes."""
from typing import Literal

from reflex import el
from reflex.vars import Var

from ..base import (
    CommonMarginProps,
    LiteralAccentColor,
    LiteralRadius,
    RadixThemesComponent,
)

LiteralSwitchSize = Literal["1", "2", "3", "4"]


class Badge(el.Span, CommonMarginProps, RadixThemesComponent):
    """A toggle switch alternative to the checkbox."""

    tag = "Badge"

    # The ratio of the width to the height of the element
    ration: Var[float]

    # The variant of the avatar
    variant: Var[Literal["solid", "soft", "surface", "outline"]]

    # The size of the avatar
    size: Var[Literal[1, 2]]

    # Color theme of the avatar
    color: Var[LiteralAccentColor]

    # Whether to render the avatar with higher contrast color against background
    high_contrast: Var[bool]

    # Override theme radius for avatar: "none" | "small" | "medium" | "large" | "full"
    radius: Var[LiteralRadius]
