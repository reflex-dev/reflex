"""Interactive components provided by @radix-ui/themes."""

from typing import Literal

from reflex.ivars.base import ImmutableVar

from ..base import (
    RadixThemesComponent,
)


class ScrollArea(RadixThemesComponent):
    """Custom styled, cross-browser scrollable area using native functionality."""

    tag = "ScrollArea"

    # The alignment of the scroll area
    scrollbars: ImmutableVar[Literal["vertical", "horizontal", "both"]]

    # Describes the nature of scrollbar visibility, similar to how the scrollbar preferences in MacOS control visibility of native scrollbars. "auto" | "always" | "scroll" | "hover"
    type: ImmutableVar[Literal["auto", "always", "scroll", "hover"]]

    # If type is set to either "scroll" or "hover", this prop determines the length of time, in milliseconds, before the scrollbars are hidden after the user stops interacting with scrollbars.
    scroll_hide_delay: ImmutableVar[int]


scroll_area = ScrollArea.create
