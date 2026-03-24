"""Radio component from Radix Themes."""

from typing import Literal

from reflex.components.component import field
from reflex.components.core.breakpoints import Responsive
from reflex.components.radix.themes.base import LiteralAccentColor, RadixThemesComponent
from reflex.vars.base import Var


class Radio(RadixThemesComponent):
    """A radio component."""

    tag = "Radio"

    size: Var[Responsive[Literal["1", "2", "3"]]] = field(
        doc='The size of the radio: "1" | "2" | "3"'
    )

    variant: Var[Literal["classic", "surface", "soft"]] = field(
        doc='Variant of button: "classic" | "surface" | "soft"'
    )

    color_scheme: Var[LiteralAccentColor] = field(doc="Override theme color for button")

    high_contrast: Var[bool] = field(
        doc="Uses a higher contrast color for the component."
    )

    # Change the default rendered element for the one passed as a child, merging their props and behavior.
    as_child = Var[bool]


radio = Radio.create
