"""Components for rendering heading.

https://www.radix-ui.com/themes/docs/theme/typography
"""

from __future__ import annotations

from reflex.components.core.breakpoints import Responsive
from reflex.components.el import elements
from reflex.ivars.base import ImmutableVar

from ..base import (
    LiteralAccentColor,
    RadixThemesComponent,
)
from .base import (
    LiteralTextAlign,
    LiteralTextSize,
    LiteralTextTrim,
    LiteralTextWeight,
)


class Heading(elements.H1, RadixThemesComponent):
    """A foundational text primitive based on the <span> element."""

    tag = "Heading"

    # Change the default rendered element for the one passed as a child, merging their props and behavior.
    as_child: ImmutableVar[bool]

    # Change the default rendered element into a semantically appropriate alternative (cannot be used with asChild)
    as_: ImmutableVar[str]

    # Text size: "1" - "9"
    size: ImmutableVar[Responsive[LiteralTextSize]]

    # Thickness of text: "light" | "regular" | "medium" | "bold"
    weight: ImmutableVar[Responsive[LiteralTextWeight]]

    # Alignment of text in element: "left" | "center" | "right"
    align: ImmutableVar[Responsive[LiteralTextAlign]]

    # Removes the leading trim space: "normal" | "start" | "end" | "both"
    trim: ImmutableVar[Responsive[LiteralTextTrim]]

    # Overrides the accent color inherited from the Theme.
    color_scheme: ImmutableVar[LiteralAccentColor]

    # Whether to render the text with higher contrast color
    high_contrast: ImmutableVar[bool]


heading = Heading.create
