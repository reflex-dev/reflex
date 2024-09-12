"""Radio component from Radix Themes."""

from typing import Literal

from reflex.components.core.breakpoints import Responsive
from reflex.ivars.base import ImmutableVar

from ..base import LiteralAccentColor, RadixThemesComponent


class Radio(RadixThemesComponent):
    """A radio component."""

    tag = "Radio"

    # The size of the radio: "1" | "2" | "3"
    size: ImmutableVar[Responsive[Literal["1", "2", "3"]]]

    # Variant of button: "classic" | "surface" | "soft"
    variant: ImmutableVar[Literal["classic", "surface", "soft"]]

    # Override theme color for button
    color_scheme: ImmutableVar[LiteralAccentColor]

    # Uses a higher contrast color for the component.
    high_contrast: ImmutableVar[bool]

    # Change the default rendered element for the one passed as a child, merging their props and behavior.
    as_child = ImmutableVar[bool]


radio = Radio.create
