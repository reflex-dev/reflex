"""Badge component."""

from reflex.components.libs.chakra import ChakraComponent, LiteralVariant
from reflex.vars import Var


class Badge(ChakraComponent):
    """A badge component."""

    tag = "Badge"

    # Variant of the badge ("solid" | "subtle" | "outline")
    variant: Var[LiteralVariant]

    # The color of the badge
    color_scheme: Var[str]
