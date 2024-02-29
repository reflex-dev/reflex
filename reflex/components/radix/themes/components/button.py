"""Interactive components provided by @radix-ui/themes."""
from typing import Literal, Optional

from reflex import el
from reflex.vars import Var

from ..base import (
    LiteralAccentColor,
    LiteralRadius,
    LiteralVariant,
    RadixThemesComponent,
)

LiteralButtonSize = Literal["1", "2", "3", "4"]


class Button(el.Button, RadixThemesComponent):
    """Trigger an action or event, such as submitting a form or displaying a dialog."""

    tag = "Button"

    # Change the default rendered element for the one passed as a child, merging their props and behavior.
    as_child: Optional[Var[bool]] = None

    # Button size "1" - "4"
    size: Optional[Var[LiteralButtonSize]] = None

    # Variant of button: "solid" | "soft" | "outline" | "ghost"
    variant: Optional[Var[LiteralVariant]] = None

    # Override theme color for button
    color_scheme: Optional[Var[LiteralAccentColor]] = None

    # Whether to render the button with higher contrast color against background
    high_contrast: Optional[Var[bool]] = None

    # Override theme radius for button: "none" | "small" | "medium" | "large" | "full"
    radius: Optional[Var[LiteralRadius]] = None


button = Button.create
