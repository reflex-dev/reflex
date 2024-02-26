"""Interactive components provided by @radix-ui/themes."""
from typing import Literal

from reflex import el
from reflex.vars import Var

from ..base import (
    LiteralAccentColor,
    LiteralRadius,
    RadixThemesComponent,
)


class Badge(el.Span, RadixThemesComponent):
    """A stylized badge element."""

    tag = "Badge"

    # The variant of the badge
    variant: Var[Literal["solid", "soft", "surface", "outline"]]

    # The size of the badge
    size: Var[Literal["1", "2"]]

    # Color theme of the badge
    color_scheme: Var[LiteralAccentColor]

    # Whether to render the badge with higher contrast color against background
    high_contrast: Var[bool]

    # Override theme radius for badge: "none" | "small" | "medium" | "large" | "full"
    radius: Var[LiteralRadius]


badge = Badge.create
