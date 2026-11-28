"""A heading."""

from __future__ import annotations

from typing import ClassVar

from reflex_base.components.component import field
from reflex_base.vars.base import Var
from reflex_components_core.core.breakpoints import Responsive
from reflex_components_core.core.markdown_component_map import MarkdownComponentMap
from reflex_components_core.el import elements

from reflex_components_ui.base import UIComponent
from reflex_components_ui.style import ComponentStyles
from reflex_components_ui.styles.heading import HEADING
from reflex_components_ui.themes import LiteralAccentColor
from reflex_components_ui.typography.base import (
    LiteralTextAlign,
    LiteralTextSize,
    LiteralTextTrim,
    LiteralTextWeight,
)


class Heading(UIComponent, elements.H1, MarkdownComponentMap):
    """A foundational text primitive based on the <span> element."""

    tag = "h1"

    styles: ClassVar[ComponentStyles] = HEADING

    _as_tags: ClassVar[frozenset[str]] = frozenset((
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
    ))

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
