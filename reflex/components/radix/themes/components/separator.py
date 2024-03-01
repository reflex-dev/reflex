"""Interactive components provided by @radix-ui/themes."""
from typing import Literal, Optional

from reflex.vars import Var

from ..base import (
    LiteralAccentColor,
    RadixThemesComponent,
)

LiteralSeperatorSize = Literal["1", "2", "3", "4"]


class Separator(RadixThemesComponent):
    """Visually or semantically separates content."""

    tag: str = "Separator"

    # The size of the select: "1" | "2" | "3" | "4"
    size: Var[LiteralSeperatorSize] = Var.create_safe("4")

    # The color of the select
    color_scheme: Optional[Var[LiteralAccentColor]] = None

    # The orientation of the separator.
    orientation: Optional[Var[Literal["horizontal", "vertical"]]] = None

    # When true, signifies that it is purely visual, carries no semantic meaning, and ensures it is not present in the accessibility tree.
    decorative: Optional[Var[bool]] = None


# Alias to divider.
divider = separator = Separator.create
