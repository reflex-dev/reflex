"""Badge component."""
from typing import Literal

from reflex.components.libs.chakra import ChakraComponent
from reflex.vars import Var


class Badge(ChakraComponent):
    """A badge component."""

    tag = "Badge"

    # Variant of the badge ("solid" | "subtle" | "outline")
    variant: Var[Literal["solid", "subtle", "outline"]]

    # The color of the badge
    color_scheme: Var[str]
