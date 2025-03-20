"""Components for rendering heading.

https://www.radix-ui.com/themes/docs/theme/typography
"""

from __future__ import annotations

from typing import Literal

from reflex.components.component import Component, MemoizationLeaf
from reflex.components.core.breakpoints import Responsive
from reflex.components.core.colors import color
from reflex.components.core.cond import cond
from reflex.components.el.elements.inline import A
from reflex.components.markdown.markdown import MarkdownComponentMap
from reflex.vars.base import Var

from ..base import LiteralAccentColor, RadixThemesComponent
from .base import LiteralTextSize, LiteralTextTrim, LiteralTextWeight

LiteralLinkUnderline = Literal["auto", "hover", "always", "none"]


class Link(RadixThemesComponent, A, MemoizationLeaf, MarkdownComponentMap):
    """A semantic element for navigation between pages."""

    tag = "Link"

    # Change the default rendered element for the one passed as a child, merging their props and behavior.
    as_child: Var[bool]

    # Text size: "1" - "9"
    size: Var[Responsive[LiteralTextSize]]

    # Thickness of text: "light" | "regular" | "medium" | "bold"
    weight: Var[Responsive[LiteralTextWeight]]

    # Removes the leading trim space: "normal" | "start" | "end" | "both"
    trim: Var[Responsive[LiteralTextTrim]]

    # Sets the visibility of the underline affordance: "auto" | "hover" | "always" | "none"
    underline: Var[LiteralLinkUnderline]

    # Overrides the accent color inherited from the Theme.
    color_scheme: Var[LiteralAccentColor]

    # Whether to render the text with higher contrast color
    high_contrast: Var[bool]

    # If True, the link will open in a new tab
    is_external: Var[bool]

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
        props.setdefault("_hover", {"color": color("accent", 8)})
        href = props.get("href")

        is_external = props.pop("is_external", None)

        if is_external is not None:
            props["target"] = cond(is_external, "_blank", "")

        if href is not None:
            if not len(children):
                raise ValueError("Link without a child will not display")
        else:
            props["href"] = "#"

        return super().create(*children, **props)


link = Link.create
