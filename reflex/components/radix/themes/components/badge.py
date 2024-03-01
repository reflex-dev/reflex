"""Interactive components provided by @radix-ui/themes."""
from typing import Literal, Optional

from reflex import el
from reflex.vars import Var

from ..base import (
    LiteralAccentColor,
    LiteralRadius,
    RadixThemesComponent,
)


class Badge(el.Span, RadixThemesComponent):
    """A stylized badge element."""

    tag: str = "Badge"

    # The variant of the badge
    variant: Optional[Var[Literal["solid", "soft", "surface", "outline"]]] = None

    # The size of the badge
    size: Optional[Var[Literal["1", "2"]]] = None

    # Color theme of the badge
    color_scheme: Optional[Var[LiteralAccentColor]] = None

    # Whether to render the badge with higher contrast color against background
    high_contrast: Optional[Var[bool]] = None

    # Override theme radius for badge: "none" | "small" | "medium" | "large" | "full"
    radius: Optional[Var[LiteralRadius]] = None


badge = Badge.create
