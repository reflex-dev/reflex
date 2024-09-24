"""Interactive components provided by @radix-ui/themes."""

from typing import Literal

from reflex.components.core.breakpoints import Responsive
from reflex.event import EventHandler
from reflex.vars.base import Var

from ..base import (
    LiteralAccentColor,
    RadixThemesComponent,
)

LiteralSwitchSize = Literal["1", "2", "3"]


class Switch(RadixThemesComponent):
    """A toggle switch alternative to the checkbox."""

    tag = "Switch"

    # Change the default rendered element for the one passed as a child, merging their props and behavior.
    as_child: Var[bool]

    # Whether the switch is checked by default
    default_checked: Var[bool]

    # Whether the switch is checked
    checked: Var[bool]

    # If true, prevent the user from interacting with the switch
    disabled: Var[bool]

    # If true, the user must interact with the switch to submit the form
    required: Var[bool]

    # The name of the switch (when submitting a form)
    name: Var[str]

    # The value associated with the "on" position
    value: Var[str]

    # Switch size "1" - "4"
    size: Var[Responsive[LiteralSwitchSize]]

    # Variant of switch: "classic" | "surface" | "soft"
    variant: Var[Literal["classic", "surface", "soft"]]

    # Override theme color for switch
    color_scheme: Var[LiteralAccentColor]

    # Whether to render the switch with higher contrast color against background
    high_contrast: Var[bool]

    # Override theme radius for switch: "none" | "small" | "full"
    radius: Var[Literal["none", "small", "full"]]

    # Props to rename
    _rename_props = {"onChange": "onCheckedChange"}

    # Fired when the value of the switch changes
    on_change: EventHandler[lambda checked: [checked]]


switch = Switch.create
