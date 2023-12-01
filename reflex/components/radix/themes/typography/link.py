"""Components for rendering heading.

https://www.radix-ui.com/themes/docs/theme/typography
"""
from __future__ import annotations

from typing import Literal

from reflex import el
from reflex.components.navigation.nextlink import NextLink
from reflex.vars import Var

from ..base import (
    CommonMarginProps,
    LiteralAccentColor,
    LiteralVariant,
    RadixThemesComponent,
)

from .base import (
    LiteralTextWeight,
    LiteralTextAlign,
    LiteralTextSize,
    LiteralTextTrim,

)

LiteralLinkUnderline = Literal["auto", "hover", "always"]


class Link(el.A, CommonMarginProps, RadixThemesComponent):
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
    color: Var[LiteralAccentColor]

    # Whether to render the text with higher contrast color
    high_contrast: Var[bool]

    @classmethod
    def create(cls, *children, **props) -> Link:
        """Create a new link.

        If the link href is a Var or does not contain a protocol, the link will be
        rendered as a NextLink for page-to-page navigation in a Next app.

        Args:
            *children: Child components.
            **props: Props for the component.
        """
        if "href" in props:
            href = props["href"]
            if isinstance(href, Var) or "://" not in href:
                props["as_child"] = True
                return super().create(NextLink.create(*children, href=props.pop("href")), **props)
        return super().create(*children, **props)