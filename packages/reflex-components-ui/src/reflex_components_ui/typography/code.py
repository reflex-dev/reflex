"""Inline code."""

from __future__ import annotations

from typing import Any, ClassVar

from reflex_base.components.component import Component, field
from reflex_base.vars.base import Var
from reflex_components_core.core.breakpoints import Responsive
from reflex_components_core.core.markdown_component_map import MarkdownComponentMap
from reflex_components_core.el import elements

from reflex_components_ui.base import UIComponent
from reflex_components_ui.props import LiteralVariant
from reflex_components_ui.style import ComponentStyles
from reflex_components_ui.styles.code import CODE
from reflex_components_ui.themes import LiteralAccentColor
from reflex_components_ui.typography.base import LiteralTextSize, LiteralTextWeight


class Code(UIComponent, elements.Code, MarkdownComponentMap):
    """A block level extended quotation."""

    tag = "code"

    styles: ClassVar[ComponentStyles] = CODE

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

    @classmethod
    def create(cls, *children, **props) -> Component:
        """Create inline code.

        Args:
            *children: The children of the component.
            **props: The props of the component.

        Returns:
            The code, which tells a link around it which variant it is: a
            link hides its underline under code that has a background.
        """
        custom_attrs: dict[str, Any] = props.setdefault("custom_attrs", {})
        custom_attrs.setdefault("data-variant", props.get("variant", "soft"))
        return super().create(*children, **props)


code = Code.create
