"""Interactive components provided by @radix-ui/themes."""
from reflex.vars import Var

from ..base import (
    RadixThemesComponent,
)


class Tooltip(RadixThemesComponent):
    """Floating element that provides a control with contextual information via pointer or focus."""

    tag = "Tooltip"

    # The content of the tooltip.
    content: Var[str]
