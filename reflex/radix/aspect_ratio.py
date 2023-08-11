"""The Radix aspect ratio component."""
from reflex.components import Component
from reflex.vars import Var


class AspectRatio(Component):
    """Base class for all aspect ratio components."""

    library = "@radix-ui/react-aspect-ratio"
    is_default = False


class AspectRatioRoot(AspectRatio):
    """Radix aspect ratio root."""

    tag = "Root"
    alias = "AspectRatioRoot"

    as_child: Var[bool]
    ratio: Var[float]
