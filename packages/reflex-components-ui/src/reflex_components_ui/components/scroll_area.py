"""A scroll area: a box that scrolls what does not fit in it."""

from __future__ import annotations

from typing import ClassVar, Literal

from reflex_base.components.component import Component, field
from reflex_base.vars.base import Var

from reflex_components_ui.base import Part, UIComponent
from reflex_components_ui.style import ComponentStyles
from reflex_components_ui.styles.scroll_area import SCROLL_AREA


class ScrollArea(UIComponent):
    """Custom styled, cross-browser scrollable area using native functionality."""

    tag = "div"

    styles: ClassVar[ComponentStyles] = SCROLL_AREA

    scrollbars: Var[Literal["vertical", "horizontal", "both"]] = field(
        doc="The alignment of the scroll area"
    )

    type: Var[Literal["auto", "always", "scroll", "hover"]] = field(
        doc='Describes the nature of scrollbar visibility, similar to how the scrollbar preferences in MacOS control visibility of native scrollbars. "auto" | "always" | "scroll" | "hover"'
    )

    scroll_hide_delay: Var[int] = field(
        doc='If type is set to either "scroll" or "hover", this prop determines the length of time, in milliseconds, before the scrollbars are hidden after the user stops interacting with scrollbars.'
    )

    def _exclude_props(self) -> list[str]:
        """Keep the props that are not attributes off the element.

        Returns:
            The props read as styles, and the delay, which the scrollbars of
            the browser do not take.
        """
        return [*super()._exclude_props(), "type", "scroll_hide_delay"]

    @classmethod
    def create(cls, *children, **props) -> Component:
        """Create a scroll area around its children.

        The area scrolls natively, with the scrollbars of the browser: no
        script runs, and it scrolls with JavaScript disabled.

        Args:
            *children: What the area scrolls.
            **props: The props of the area.

        Returns:
            The scroll area.
        """
        return super().create(
            Part.create(*children, part="content", tag="div"), **props
        )


scroll_area = ScrollArea.create
