"""Components for rendering heading.

https://www.radix-ui.com/themes/docs/theme/typography
"""

from __future__ import annotations

from reflex.components.component import field
from reflex.components.core.breakpoints import Responsive
from reflex.components.el import elements
from reflex.components.markdown.markdown import MarkdownComponentMap
from reflex.components.radix.themes.base import (
    LiteralAccentColor,
    LiteralVariant,
    RadixThemesComponent,
)
from reflex.vars.base import Var

from .base import LiteralTextSize, LiteralTextWeight


class Code(elements.Code, RadixThemesComponent, MarkdownComponentMap):
    """A block level extended quotation."""

    tag = "Code"

    variant: Var[LiteralVariant] = field(
        doc='The visual variant to apply: "solid" | "soft" | "outline" | "ghost"'
    )

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


code = Code.create
