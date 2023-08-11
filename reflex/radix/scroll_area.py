"""The Radix scroll area component."""
from typing import Literal

from reflex.components import Component
from reflex.vars import Var


class ScrollAreaComponent(Component):
    """Base class for all scroll area components."""

    library = "@radix-ui/react-scroll-area"
    is_default = False

    as_child: Var[bool]


class ScrollAreaRoot(ScrollAreaComponent):
    """Radix scroll area root."""

    tag = "Root"
    alias = "ScrollAreaRoot"

    type_: Var[Literal["auto", "always", "scroll", "hover"]]
    scroll_hide_delay: Var[int]
    dir: Var[Literal["ltr", "rtl"]]


class ScrollAreaViewport(ScrollAreaComponent):
    """Radix scroll area viewport."""

    tag = "Viewport"
    alias = "ScrollAreaViewport"


class ScrollAreaScrollbar(ScrollAreaComponent):
    """Radix scroll area scrollbar."""

    tag = "Scrollbar"
    alias = "ScrollAreaScrollbar"

    force_mount: Var[bool]
    orientation: Var[Literal["vertical", "horizontal"]]


class ScrollAreaThumb(ScrollAreaComponent):
    """Radix scroll area thumb."""

    tag = "Thumb"
    alias = "ScrollAreaThumb"


class ScrollAreaCorner(ScrollAreaComponent):
    """Radix scroll area corner."""

    tag = "Corner"
    alias = "ScrollAreaCorner"
