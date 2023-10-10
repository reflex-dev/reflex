"""A line to divide parts of the layout."""
from typing import Literal

from reflex.components.libs.chakra import ChakraComponent
from reflex.vars import Var


class Divider(ChakraComponent):
    """Dividers are used to visually separate content in a list or group."""

    tag = "Divider"

    # Pass the orientation prop and set it to either horizontal or vertical. If the vertical orientation is used, make sure that the parent element is assigned a height.
    orientation: Var[Literal["horizontal", "vertical"]]

    # Variant of the divider ("solid" | "dashed")
    variant: Var[Literal["solid", "dashed"]]
