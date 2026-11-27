"""A block quotation."""

from __future__ import annotations

from typing import ClassVar

from reflex_base.components.component import field
from reflex_base.vars.base import Var
from reflex_components_core.core.breakpoints import Responsive
from reflex_components_core.el import elements

from reflex_components_ui.base import UIComponent
from reflex_components_ui.style import ComponentStyles
from reflex_components_ui.styles.blockquote import BLOCKQUOTE
from reflex_components_ui.themes import LiteralAccentColor
from reflex_components_ui.typography.base import LiteralTextSize, LiteralTextWeight


class Blockquote(UIComponent, elements.Blockquote):
    """A block level extended quotation."""

    tag = "blockquote"

    styles: ClassVar[ComponentStyles] = BLOCKQUOTE

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
