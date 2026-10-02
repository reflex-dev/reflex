"""Interactive components provided by @radix-ui/themes."""

from typing import Literal

from reflex_base.components.component import field
from reflex_base.vars.base import Var

from reflex_components_radix.themes.base import RadixThemesComponent


class ScrollArea(RadixThemesComponent):
    """Custom styled, cross-browser scrollable area using native functionality."""

    tag = "ScrollArea"

    scrollbars: Var[Literal["vertical", "horizontal", "both"]] = field(
        doc="The alignment of the scroll area"
    )

    type: Var[Literal["auto", "always", "scroll", "hover"]] = field(
        doc='Describes the nature of scrollbar visibility, similar to how the scrollbar preferences in MacOS control visibility of native scrollbars. "auto" | "always" | "scroll" | "hover"'
    )

    scroll_hide_delay: Var[int] = field(
        doc='If type is set to either "scroll" or "hover", this prop determines the length of time, in milliseconds, before the scrollbars are hidden after the user stops interacting with scrollbars.'
    )


scroll_area = ScrollArea.create
