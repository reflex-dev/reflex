"""Components for rendering heading.

https://www.radix-ui.com/themes/docs/theme/typography
"""

from __future__ import annotations

from reflex.components.core.breakpoints import Responsive
from reflex.components.el import elements
from reflex.ivars.base import ImmutableVar

from ..base import (
    LiteralAccentColor,
    LiteralVariant,
    RadixThemesComponent,
)
from .base import (
    LiteralTextSize,
    LiteralTextWeight,
)


class Code(elements.Code, RadixThemesComponent):
    """A block level extended quotation."""

    tag = "Code"

    # The visual variant to apply: "solid" | "soft" | "outline" | "ghost"
    variant: ImmutableVar[LiteralVariant]

    # Text size: "1" - "9"
    size: ImmutableVar[Responsive[LiteralTextSize]]

    # Thickness of text: "light" | "regular" | "medium" | "bold"
    weight: ImmutableVar[Responsive[LiteralTextWeight]]

    # Overrides the accent color inherited from the Theme.
    color_scheme: ImmutableVar[LiteralAccentColor]

    # Whether to render the text with higher contrast color
    high_contrast: ImmutableVar[bool]


code = Code.create
