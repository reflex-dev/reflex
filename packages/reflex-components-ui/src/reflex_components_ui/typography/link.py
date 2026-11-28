"""A link, which navigates within the app without loading a page."""

from __future__ import annotations

from typing import ClassVar, Literal

from reflex_base.components.component import Component, MemoizationLeaf, field
from reflex_base.vars.base import Var
from reflex_components_core.core.breakpoints import Responsive
from reflex_components_core.core.cond import cond
from reflex_components_core.core.markdown_component_map import MarkdownComponentMap
from reflex_components_core.el.elements.inline import A
from reflex_components_core.react_router.dom import ReactRouterLink

from reflex_components_ui import tokens
from reflex_components_ui.base import UIComponent
from reflex_components_ui.style import ComponentStyles
from reflex_components_ui.styles.link import LINK
from reflex_components_ui.themes import LiteralAccentColor
from reflex_components_ui.typography.base import (
    LiteralTextSize,
    LiteralTextTrim,
    LiteralTextWeight,
)

LiteralLinkUnderline = Literal["auto", "hover", "always", "none"]

_KNOWN_REACT_ROUTER_LINK_PROPS = frozenset(ReactRouterLink.get_props())


class Link(UIComponent, A, MemoizationLeaf, MarkdownComponentMap):
    """A semantic element for navigation between pages."""

    tag = "a"

    styles: ClassVar[ComponentStyles] = LINK

    as_child: Var[bool] = field(
        doc="Change the default rendered element for the one passed as a child, merging their props and behavior."
    )

    size: Var[Responsive[LiteralTextSize]] = field(doc='Text size: "1" - "9"')

    weight: Var[Responsive[LiteralTextWeight]] = field(
        doc='Thickness of text: "light" | "regular" | "medium" | "bold"'
    )

    trim: Var[Responsive[LiteralTextTrim]] = field(
        doc='Removes the leading trim space: "normal" | "start" | "end" | "both"'
    )

    underline: Var[LiteralLinkUnderline] = field(
        doc='Sets the visibility of the underline affordance: "auto" | "hover" | "always" | "none"'
    )

    color_scheme: Var[LiteralAccentColor] = field(
        doc="Overrides the accent color inherited from the Theme."
    )

    high_contrast: Var[bool] = field(
        doc="Whether to render the text with higher contrast color"
    )

    is_external: Var[bool] = field(doc="If True, the link will open in a new tab")

    @classmethod
    def create(cls, *children, **props) -> Component:
        """Create a Link component.

        Args:
            *children: The children of the component.
            **props: The props of the component.

        Returns:
            Component: The link component

        Raises:
            ValueError: in case of missing children
        """
        props.setdefault("_hover", {"color": tokens.accent[8]})
        href = props.get("href")

        is_external = props.pop("is_external", None)

        if is_external is not None:
            props["target"] = cond(is_external, "_blank", "")

        if href is not None:
            if not len(children):
                msg = "Link without a child will not display"
                raise ValueError(msg)

            if "as_child" not in props:
                # Extract props for the ReactRouterLink, the rest go to the Link/A element.
                react_router_link_props = {}
                for prop in props.copy():
                    if prop in _KNOWN_REACT_ROUTER_LINK_PROPS:
                        react_router_link_props[prop] = props.pop(prop)

                react_router_link_props["to"] = react_router_link_props.pop(
                    "href", href
                )

                # Without `as_child`, the link of the router is the element:
                # an internal navigation does not load the page again.
                return super().create(
                    ReactRouterLink.create(*children, **react_router_link_props),
                    as_child=True,
                    **props,
                )
        else:
            props["href"] = "#"

        return super().create(*children, **props)


link = Link.create
