"""Interactive components provided by @radix-ui/themes."""
from typing import Literal, Union

import reflex as rx
from reflex import el
from reflex.components.component import Component
from reflex.components.radix.themes.components.icons import Icon
from reflex.vars import Var

from ..base import (
    LiteralAccentColor,
    RadixThemesComponent,
)

CalloutVariant = Literal["soft", "surface", "outline"]


class CalloutRoot(el.Div, RadixThemesComponent):
    """Trigger an action or event, such as submitting a form or displaying a dialog."""

    tag = "Callout.Root"

    # Change the default rendered element for the one passed as a child, merging their props and behavior.
    as_child: Var[bool]

    # Size "1" - "3"
    size: Var[Literal["1", "2", "3"]]

    # Variant of button: "soft" | "surface" | "outline"
    variant: Var[CalloutVariant]

    # Override theme color for button
    color_scheme: Var[LiteralAccentColor]

    # Whether to render the button with higher contrast color against background
    high_contrast: Var[bool]


class CalloutIcon(el.Div, RadixThemesComponent):
    """Trigger an action or event, such as submitting a form or displaying a dialog."""

    tag = "Callout.Icon"


class CalloutText(el.P, RadixThemesComponent):
    """Trigger an action or event, such as submitting a form or displaying a dialog."""

    tag = "Callout.Text"


class Callout(CalloutRoot):
    """High level wrapper for the Callout component."""

    # The text of the callout.
    text: Var[str]

    # The icon of the callout.
    icon: Var[str]

    @classmethod
    def create(cls, text: Union[str, Var[str]], **props) -> Component:
        """Create a callout component.

        Args:
            text: The text of the callout.
            **props: The properties of the component.

        Returns:
            The callout component.
        """
        return CalloutRoot.create(
            CalloutIcon.create(Icon.create(tag=props["icon"]))
            if "icon" in props
            else rx.fragment(),
            CalloutText.create(text),
            **props,
        )
