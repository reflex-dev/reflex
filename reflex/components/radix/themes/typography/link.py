"""Components for rendering heading.

https://www.radix-ui.com/themes/docs/theme/typography
"""
from __future__ import annotations

from typing import Literal

from reflex.components.component import Component
from reflex.components.el.elements.inline import A
from reflex.components.next.link import NextLink
from reflex.utils import imports
from reflex.vars import Var

from ..base import (
    LiteralAccentColor,
    RadixThemesComponent,
)
from .base import (
    LiteralTextSize,
    LiteralTextTrim,
    LiteralTextWeight,
)

LiteralLinkUnderline = Literal["auto", "hover", "always"]

next_link = NextLink.create()


class Link(RadixThemesComponent, A):
    """A semantic element for navigation between pages."""

    tag = "Link"

    # Change the default rendered element for the one passed as a child, merging their props and behavior.
    as_child: Var[bool]

    # Text size: "1" - "9"
    size: Var[LiteralTextSize]

    # Thickness of text: "light" | "regular" | "medium" | "bold"
    weight: Var[LiteralTextWeight]

    # Removes the leading trim space: "normal" | "start" | "end" | "both"
    trim: Var[LiteralTextTrim]

    # Sets the visibility of the underline affordance: "auto" | "hover" | "always"
    underline: Var[LiteralLinkUnderline]

    # Overrides the accent color inherited from the Theme.
    color_scheme: Var[LiteralAccentColor]

    # Whether to render the text with higher contrast color
    high_contrast: Var[bool]

    def _get_imports(self) -> imports.ImportDict:
        return {**super()._get_imports(), **next_link._get_imports()}

    @classmethod
    def create(cls, *children, **props) -> Component:
        """Create a Link component.

        Args:
            *children: The children of the component.
            **props: The props of the component.

        Raises:
            ValueError: in case of missing children

        Returns:
            Component: The link component
        """
        if props.get("href") is not None:
            if not len(children):
                raise ValueError("Link without a child will not display")
            if "as_child" not in props:
                # If user does not use `as_child`, by default we render using next_link to avoid page refresh during internal navigation
                return super().create(
                    NextLink.create(*children, **props), as_child=True
                )
        return super().create(*children, **props)
