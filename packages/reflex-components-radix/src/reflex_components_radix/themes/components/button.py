"""Interactive components provided by @radix-ui/themes."""

from typing import Literal

from reflex_base.components.component import field
from reflex_base.vars.base import Var
from reflex_components_core.core.breakpoints import Responsive
from reflex_components_core.el import elements

from reflex_components_radix.themes.base import (
    LiteralAccentColor,
    LiteralRadius,
    LiteralVariant,
    RadixLoadingProp,
    RadixThemesComponent,
)

LiteralButtonSize = Literal["1", "2", "3", "4"]


class Button(elements.Button, RadixLoadingProp, RadixThemesComponent):
    """Trigger an action or event, such as submitting a form or displaying a dialog."""

    tag = "Button"

    as_child: Var[bool] = field(
        doc="Change the default rendered element for the one passed as a child, merging their props and behavior."
    )

    size: Var[Responsive[LiteralButtonSize]] = field(doc='Button size "1" - "4"')

    variant: Var[LiteralVariant] = field(
        doc='Variant of button: "solid" | "soft" | "outline" | "ghost"'
    )

    color_scheme: Var[LiteralAccentColor] = field(doc="Override theme color for button")

    high_contrast: Var[bool] = field(
        doc="Whether to render the button with higher contrast color against background"
    )

    radius: Var[LiteralRadius] = field(
        doc='Override theme radius for button: "none" | "small" | "medium" | "large" | "full"'
    )


button = Button.create
