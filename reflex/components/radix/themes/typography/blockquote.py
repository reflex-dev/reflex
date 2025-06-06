"""Components for rendering heading.

https://www.radix-ui.com/themes/docs/theme/typography
"""

from __future__ import annotations

from reflex.components.core.breakpoints import Responsive
from reflex.components.el import elements
from reflex.components.radix.themes.base import LiteralAccentColor, RadixThemesComponent
from reflex.vars.base import Var

from .base import LiteralTextSize, LiteralTextWeight


class Blockquote(elements.Blockquote, RadixThemesComponent):
    """A block level extended quotation."""

    tag = "Blockquote"

    # Text size: "1" - "9"
    size: Var[Responsive[LiteralTextSize]]

    # Thickness of text: "light" | "regular" | "medium" | "bold"
    weight: Var[Responsive[LiteralTextWeight]]

    # Overrides the accent color inherited from the Theme.
    color_scheme: Var[LiteralAccentColor]

    # Whether to render the text with higher contrast color
    high_contrast: Var[bool]


blockquote = Blockquote.create
