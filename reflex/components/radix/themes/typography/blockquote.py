"""Components for rendering heading.

https://www.radix-ui.com/themes/docs/theme/typography
"""

from __future__ import annotations

from reflex.components.component import field
from reflex.components.core.breakpoints import Responsive
from reflex.components.el import elements
from reflex.components.radix.themes.base import LiteralAccentColor, RadixThemesComponent
from reflex.vars.base import Var

from .base import LiteralTextSize, LiteralTextWeight


class Blockquote(elements.Blockquote, RadixThemesComponent):
    """A block level extended quotation."""

    tag = "Blockquote"

    size: Var[Responsive[LiteralTextSize]] = field(doc='Text size: "1" - "9"')

    weight: Var[Responsive[LiteralTextWeight]] = field(
        doc='Thickness of text: "light" | "regular" | "medium" | "bold"'
    )

    color_scheme: Var[LiteralAccentColor] = field(
        doc="Overrides the accent color inherited from the Theme."
    )

    high_contrast: Var[bool] = field(
        doc="Whether to render the text with higher contrast color"
    )


blockquote = Blockquote.create
