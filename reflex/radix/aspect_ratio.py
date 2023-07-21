"""The Radix aspect ratio component."""
from typing import Optional

from reflex.components import Component


class AspectRatio(Component):
    """Base class for all aspect ratio components."""

    library = "@radix-ui/react-aspect-ratio"
    is_default = False


class AspectRatioRoot(AspectRatio):
    """Radix aspect ratio root."""

    tag = "Root"
    alias = "AspectRatioRoot"

    as_child: Optional[bool]
    ratio: Optional[float]
