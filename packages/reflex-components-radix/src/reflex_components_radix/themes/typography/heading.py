"""Components for rendering heading.

https://www.radix-ui.com/themes/docs/theme/typography
"""

from __future__ import annotations

from reflex_base.components.component import field
from reflex_base.vars.base import Var
from reflex_components_core.core.breakpoints import Responsive
from reflex_components_core.core.markdown_component_map import MarkdownComponentMap
from reflex_components_core.el import elements

from reflex_components_radix.themes.base import LiteralAccentColor, RadixThemesComponent

from .base import LiteralTextAlign, LiteralTextSize, LiteralTextTrim, LiteralTextWeight


class Heading(elements.H1, RadixThemesComponent, MarkdownComponentMap):
    """A foundational text primitive based on the <span> element."""

    tag = "Heading"

    as_child: Var[bool] = field(
        doc="Change the default rendered element for the one passed as a child, merging their props and behavior."
    )

    as_: Var[str] = field(
        doc="Change the default rendered element into a semantically appropriate alternative (cannot be used with asChild)"
    )

    size: Var[Responsive[LiteralTextSize]] = field(doc='Text size: "1" - "9"')

    weight: Var[Responsive[LiteralTextWeight]] = field(
        doc='Thickness of text: "light" | "regular" | "medium" | "bold"'
    )

    align: Var[Responsive[LiteralTextAlign]] = field(
        doc='Alignment of text in element: "left" | "center" | "right"'
    )

    trim: Var[Responsive[LiteralTextTrim]] = field(
        doc='Removes the leading trim space: "normal" | "start" | "end" | "both"'
    )

    color_scheme: Var[LiteralAccentColor] = field(
        doc="Overrides the accent color inherited from the Theme."
    )

    high_contrast: Var[bool] = field(
        doc="Whether to render the text with higher contrast color"
    )


heading = Heading.create
