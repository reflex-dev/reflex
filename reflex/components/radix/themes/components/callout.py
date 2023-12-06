"""Interactive components provided by @radix-ui/themes."""
from typing import Literal

from reflex import el
from reflex.vars import Var

from ..base import (
    CommonMarginProps,
    LiteralAccentColor,
    LiteralRadius,
    LiteralVariant,
    RadixThemesComponent,
)


class CalloutRoot(el.Div, CommonMarginProps, RadixThemesComponent):
    """Trigger an action or event, such as submitting a form or displaying a dialog."""

    tag = "Callout.Root"

    # Change the default rendered element for the one passed as a child, merging their props and behavior.
    as_child: Var[bool]

    # Button size "1" - "4"
    size: Var[Literal["1", "2", "3"]]

    # Variant of button: "solid" | "soft" | "outline" | "ghost"
    variant: Var[LiteralVariant]

    # Override theme color for button
    color: Var[LiteralAccentColor]

    # Whether to render the button with higher contrast color against background
    high_contrast: Var[bool]

    # Override theme radius for button: "none" | "small" | "medium" | "large" | "full"
    radius: Var[LiteralRadius]


class CalloutIcon(el.Div, CommonMarginProps, RadixThemesComponent):
    """Trigger an action or event, such as submitting a form or displaying a dialog."""

    tag = "Callout.Icon"


class CalloutText(el.P, CommonMarginProps, RadixThemesComponent):
    """Trigger an action or event, such as submitting a form or displaying a dialog."""

    tag = "Callout.Text"
