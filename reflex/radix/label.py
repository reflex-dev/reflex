"""The Radix label component."""
from typing import Optional

from reflex.components import Component


class LabelRoot(Component):
    """Radix label root."""

    library = "@radix-ui/react-label"
    is_default = False

    tag = "Root"
    alias = "LabelRoot"

    as_child: Optional[bool]
    html_for: Optional[str]
