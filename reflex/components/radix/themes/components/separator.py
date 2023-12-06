"""Interactive components provided by @radix-ui/themes."""
from typing import Literal

from reflex.vars import Var

from ..base import (
    CommonMarginProps,
    LiteralAccentColor,
    RadixThemesComponent,
)

LiteralSeperatorSize = Literal["1", "2", "3", "4"]


class Separator(CommonMarginProps, RadixThemesComponent):
    """Trigger an action or event, such as submitting a form or displaying a dialog."""

    tag = "Separator"

    # The size of the select: "1" | "2" | "3"
    size: Var[LiteralSeperatorSize]

    # The color of the select
    color: Var[LiteralAccentColor]

    # The orientation of the separator.
    orientation: Var[Literal["horizontal", "vertical"]]

    # When true, signifies that it is purely visual, carries no semantic meaning, and ensures it is not present in the accessibility tree.
    decorative: Var[bool]
