"""Interactive components provided by @radix-ui/themes."""

from typing import Literal

from reflex.components.core.breakpoints import Responsive
from reflex.components.el import elements
from reflex.vars.base import Var

from ..base import LiteralAccentColor, LiteralRadius, RadixThemesComponent


class Badge(elements.Span, RadixThemesComponent):
    """A stylized badge element."""

    tag = "Badge"

    # The variant of the badge
    variant: Var[Literal["solid", "soft", "surface", "outline"]]

    # The size of the badge
    size: Var[Responsive[Literal["1", "2", "3"]]]

    # Color theme of the badge
    color_scheme: Var[LiteralAccentColor]

    # Whether to render the badge with higher contrast color against background
    high_contrast: Var[bool]

    # Override theme radius for badge: "none" | "small" | "medium" | "large" | "full"
    radius: Var[LiteralRadius]


badge = Badge.create
