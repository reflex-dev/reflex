"""Components for rendering heading.

https://www.radix-ui.com/themes/docs/theme/typography
"""

from __future__ import annotations

from reflex_base.components.component import field
from reflex_base.vars.base import Var
from reflex_components_core.core.breakpoints import Responsive
from reflex_components_core.el import elements

from reflex_components_radix.themes.base import LiteralAccentColor, RadixThemesComponent

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
