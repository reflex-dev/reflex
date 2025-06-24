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
from reflex.components.radix.themes.base import LiteralAccentColor, RadixThemesComponent
from reflex.utils.imports import ImportDict, ImportVar
from reflex.vars.base import Var

from .base import LiteralTextSize, LiteralTextTrim, LiteralTextWeight

LiteralLinkUnderline = Literal["auto", "hover", "always", "none"]

LiteralLinkDiscover = Literal["none", "render"]


class ReactRouterLink(A):
    """Links are accessible elements used primarily for navigation. This component is styled to resemble a hyperlink and semantically renders an <a>."""

    library = "react-router"

    tag = "Link"

    alias = "ReactRouterLink"

    # The page to link to.
    to: Var[str]

    # Replaces the current entry in the history stack instead of pushing a new one onto it.
    replace: Var[bool]

    # Will use document navigation instead of client side routing when the link is clicked: the browser will handle the transition normally (as if it were an <a href>).
    reload_document: Var[bool]

    # Prevents the scroll position from being reset to the top of the window when the link is clicked and the app is using ScrollRestoration. This only prevents new locations resetting scroll to the top, scroll position will be restored for back/forward button navigation.
    prevent_scroll_reset: Var[bool]

    # Defines the link discovery behavior
    discover: Var[LiteralLinkDiscover]

    # Enables a View Transition for this navigation.
    view_transition: Var[bool]


_KNOWN_REACT_ROUTER_LINK_PROPS = frozenset(ReactRouterLink.get_props())


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
