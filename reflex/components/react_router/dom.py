"""Components for client side navigation within React Router applications."""

from __future__ import annotations

from typing import ClassVar, Literal, TypedDict

from reflex.components.el.elements.inline import A
from reflex.vars.base import Var

LiteralLinkDiscover = Literal["none", "render"]


class To(TypedDict):
    """Structured object for navigating via the `to` prop."""

    # A URL pathname, beginning with a /
    pathname: str

    # A URL search string, beginning with a ?.
    search: str

    # A URL fragment identifier, beginning with a #.
    hash: str


class ReactRouterLink(A):
    """Links are accessible elements used primarily for navigation. This component is styled to resemble a hyperlink and semantically renders an <a>."""

    library = "react-router"

    tag = "Link"

    alias = "ReactRouterLink"

    # The page to link to.
    to: Var[str | To]

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

    @classmethod
    def create(cls, *children, **props):
        """Create a ReactRouterLink component for client-side navigation.

        Args:
            *children: The children of the component.
            **props: The props of the component.

        Returns:
            The ReactRouterLink component.
        """
        # React Router special behavior is triggered on the `to` prop, not href.
        if "to" not in props and "href" in props:
            props["to"] = props.pop("href")
        return super().create(*children, **props)

    _invalid_children: ClassVar[list[str]] = ["A", "ReactRouterLink"]
