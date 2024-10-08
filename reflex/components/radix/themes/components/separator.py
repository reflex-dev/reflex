"""Interactive components provided by @radix-ui/themes."""

from typing import Literal

from reflex.components.core.breakpoints import Responsive
from reflex.vars.base import LiteralVar, Var

from ..base import (
    LiteralAccentColor,
    RadixThemesComponent,
)

LiteralSeperatorSize = Literal["1", "2", "3", "4"]


class Separator(RadixThemesComponent):
    """Visually or semantically separates content."""

    tag = "Separator"

    # The size of the select: "1" | "2" | "3" | "4"
    size: Var[Responsive[LiteralSeperatorSize]] = LiteralVar.create("4")

    # The color of the select
    color_scheme: Var[LiteralAccentColor]

    # The orientation of the separator.
    orientation: Var[Responsive[Literal["horizontal", "vertical"]]]

    # When true, signifies that it is purely visual, carries no semantic meaning, and ensures it is not present in the accessibility tree.
    decorative: Var[bool]


# Alias to divider.
divider = separator = Separator.create
