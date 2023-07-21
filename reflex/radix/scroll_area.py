"""The Radix scroll area component."""
from typing import Literal, Optional

from reflex.components import Component


class ScrollAreaComponent(Component):
    """Base class for all scroll area components."""

    library = "@radix-ui/react-scroll-area"
    is_default = False

    as_child: Optional[bool]


class ScrollAreaRoot(ScrollAreaComponent):
    """Radix scroll area root."""

    tag = "Root"
    alias = "ScrollAreaRoot"

    type: Optional[Literal["auto", "always", "scroll", "hover"]]
    scroll_hide_delay: Optional[int]
    dir: Optional[Literal["ltr", "rtl"]]


class ScrollAreaViewport(ScrollAreaComponent):
    """Radix scroll area viewport."""

    tag = "Viewport"
    alias = "ScrollAreaViewport"


class ScrollAreaScrollbar(ScrollAreaComponent):
    """Radix scroll area scrollbar."""

    tag = "Scrollbar"
    alias = "ScrollAreaScrollbar"

    force_mount: Optional[bool]
    orientation: Optional[Literal["vertical", "horizontal"]]


class ScrollAreaThumb(ScrollAreaComponent):
    """Radix scroll area thumb."""

    tag = "Thumb"
    alias = "ScrollAreaThumb"


class ScrollAreaCorner(ScrollAreaComponent):
    """Radix scroll area corner."""

    tag = "Corner"
    alias = "ScrollAreaCorner"
