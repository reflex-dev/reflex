"""Interactive components provided by @radix-ui/themes."""

from typing import Literal

from reflex.components.core.breakpoints import Responsive
from reflex.components.el import elements
from reflex.components.radix.themes.base import (
    LiteralAccentColor,
    LiteralRadius,
    LiteralVariant,
    RadixLoadingProp,
    RadixThemesComponent,
)
from reflex.vars.base import Var

LiteralButtonSize = Literal["1", "2", "3", "4"]


class Button(elements.Button, RadixLoadingProp, RadixThemesComponent):
    """Trigger an action or event, such as submitting a form or displaying a dialog."""

    tag = "Button"

    # Change the default rendered element for the one passed as a child, merging their props and behavior.
    as_child: Var[bool]

    # Button size "1" - "4"
    size: Var[Responsive[LiteralButtonSize]]

    # Variant of button: "solid" | "soft" | "outline" | "ghost"
    variant: Var[LiteralVariant]

    # Override theme color for button
    color_scheme: Var[LiteralAccentColor]

    # Whether to render the button with higher contrast color against background
    high_contrast: Var[bool]

    # Override theme radius for button: "none" | "small" | "medium" | "large" | "full"
    radius: Var[LiteralRadius]


button = Button.create
