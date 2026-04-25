"""Interactive components provided by @radix-ui/themes."""

from typing import Literal

from reflex_base.components.component import field
from reflex_base.vars.base import LiteralVar, Var
from reflex_components_core.core.breakpoints import Responsive

from reflex_components_radix.themes.base import LiteralAccentColor, RadixThemesComponent

LiteralSeparatorSize = Literal["1", "2", "3", "4"]


class Separator(RadixThemesComponent):
    """Visually or semantically separates content."""

    tag = "Separator"

    size: Var[Responsive[LiteralSeparatorSize]] = field(
        default=LiteralVar.create("4"),
        doc='The size of the separator: "1" | "2" | "3" | "4"',
    )

    color_scheme: Var[LiteralAccentColor] = field(doc="The color of the separator")

    orientation: Var[Responsive[Literal["horizontal", "vertical"]]] = field(
        doc="The orientation of the separator."
    )

    decorative: Var[bool] = field(
        doc="When true, signifies that it is purely visual, carries no semantic meaning, and ensures it is not present in the accessibility tree."
    )


# Alias to divider.
divider = separator = Separator.create
