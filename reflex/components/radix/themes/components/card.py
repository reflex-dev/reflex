"""Interactive components provided by @radix-ui/themes."""
from typing import Literal

from reflex import el
from reflex.vars import Var

from ..base import (
    CommonMarginProps,
    RadixThemesComponent,
)


class Card(el.Div, CommonMarginProps, RadixThemesComponent):
    """Trigger an action or event, such as submitting a form or displaying a dialog."""

    tag = "Card"

    # Change the default rendered element for the one passed as a child, merging their props and behavior.
    as_child: Var[bool]

    # Button size "1" - "5"
    size: Var[Literal["1", "2", "3", "4", "5"]]

    # Variant of button: "solid" | "soft" | "outline" | "ghost"
    variant: Var[Literal["surface", "classic", "ghost"]]
