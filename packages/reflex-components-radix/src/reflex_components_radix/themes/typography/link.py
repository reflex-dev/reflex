"""Components for rendering heading.

https://www.radix-ui.com/themes/docs/theme/typography
"""

from __future__ import annotations

from typing import Literal

from reflex_base.components.component import Component, MemoizationLeaf, field
from reflex_base.utils.imports import ImportDict, ImportVar
from reflex_base.vars.base import Var
from reflex_components_core.core.breakpoints import Responsive
from reflex_components_core.core.colors import color
from reflex_components_core.core.cond import cond
from reflex_components_core.core.markdown_component_map import MarkdownComponentMap
from reflex_components_core.el.elements.inline import A
from reflex_components_core.react_router.dom import ReactRouterLink

from reflex_components_radix.themes.base import LiteralAccentColor, RadixThemesComponent

from .base import LiteralTextSize, LiteralTextTrim, LiteralTextWeight

LiteralLinkUnderline = Literal["auto", "hover", "always", "none"]


_KNOWN_REACT_ROUTER_LINK_PROPS = frozenset(ReactRouterLink.get_props())


class Link(RadixThemesComponent, A, MemoizationLeaf, MarkdownComponentMap):
    """A semantic element for navigation between pages."""

    tag = "Link"

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

    def add_imports(self) -> ImportDict:
        """Add imports for the Link component.

        Returns:
            The import dict.
        """
        return {
            "react-router": [ImportVar(tag="Link", alias="ReactRouterLink")],
        }

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
        props.setdefault("_hover", {"color": color("accent", 8)})
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

                # If user does not use `as_child`, by default we render using react_router_link to avoid page refresh during internal navigation
                return super().create(
                    ReactRouterLink.create(*children, **react_router_link_props),
                    as_child=True,
                    **props,
                )
        else:
            props["href"] = "#"

        return super().create(*children, **props)


link = Link.create
