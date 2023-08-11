"""The Radix separator component."""
from typing import Literal

from reflex.components import Component
from reflex.vars import Var


class Separator(Component):
    """Radix separator."""

    library = "@radix-ui/react-separator"

    tag = "Separator"

    # The orientation of the separator. Defaults to "horizontal".
    orientation: Var[str]

    # Whether the separator is decorative or not.
    decorative: Var[bool]

    # Whether to use a child.
    as_child: Var[bool]
