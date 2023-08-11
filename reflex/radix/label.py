"""The Radix label component."""
from reflex.components import Component
from reflex.vars import Var


class LabelRoot(Component):
    """Radix label root."""

    library = "@radix-ui/react-label"
    is_default = False

    tag = "Root"
    alias = "LabelRoot"

    as_child: Var[bool]
    html_for: Var[str]
