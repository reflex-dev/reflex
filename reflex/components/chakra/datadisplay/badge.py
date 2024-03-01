"""Badge component."""
from typing import Optional

from reflex.components.chakra import ChakraComponent, LiteralVariant
from reflex.vars import Var


class Badge(ChakraComponent):
    """A badge component."""

    tag: str = "Badge"

    # Variant of the badge ("solid" | "subtle" | "outline")
    variant: Optional[Var[LiteralVariant]] = None

    # The color of the badge
    color_scheme: Optional[Var[str]] = None
