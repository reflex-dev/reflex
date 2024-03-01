"""A line to divide parts of the layout."""
from typing import Literal, Optional

from reflex.components.chakra import ChakraComponent, LiteralDividerVariant
from reflex.vars import Var

LiteralLayout = Literal["horizontal", "vertical"]


class Divider(ChakraComponent):
    """Dividers are used to visually separate content in a list or group."""

    tag: str = "Divider"

    # Pass the orientation prop and set it to either horizontal or vertical. If the vertical orientation is used, make sure that the parent element is assigned a height.
    orientation: Optional[Var[LiteralLayout]] = None

    # Variant of the divider ("solid" | "dashed")
    variant: Optional[Var[LiteralDividerVariant]] = None
