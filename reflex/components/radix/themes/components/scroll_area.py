"""Interactive components provided by @radix-ui/themes."""

from typing import Literal

from reflex.vars import Var

from ..base import (
    RadixThemesComponent,
)


class ScrollArea(RadixThemesComponent):
    """Custom styled, cross-browser scrollable area using native functionality."""

    tag = "ScrollArea"

    # The alignment of the scroll area
    scrollbars: Var[Literal["vertical", "horizontal", "both"]]

    # Describes the nature of scrollbar visibility, similar to how the scrollbar preferences in MacOS control visibility of native scrollbars. "auto" | "always" | "scroll" | "hover"
    type: Var[Literal["auto", "always", "scroll", "hover"]]

    # If type is set to either "scroll" or "hover", this prop determines the length of time, in milliseconds, before the scrollbars are hidden after the user stops interacting with scrollbars.
    scroll_hide_delay: Var[int]


scroll_area = ScrollArea.create
