"""The Radix separator component."""
from typing import Literal, Optional

from reflex.components import Component


class Separator(Component):
    """Radix separator."""

    library = "@radix-ui/react-separator"

    tag = "Separator"

    # The orientation of the separator. Defaults to "horizontal".
    orientation: Optional[Literal["horizontal"] | Literal["vertical"]]

    # Whether the separator is decorative or not.
    decorative: Optional[bool]

    # Whether to use a child.
    as_child: Optional[bool]
