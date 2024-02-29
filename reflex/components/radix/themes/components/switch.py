"""Interactive components provided by @radix-ui/themes."""
from typing import Any, Dict, Literal, Optional

from reflex.constants import EventTriggers
from reflex.vars import Var

from ..base import (
    LiteralAccentColor,
    RadixThemesComponent,
)

LiteralSwitchSize = Literal["1", "2", "3"]


class Switch(RadixThemesComponent):
    """A toggle switch alternative to the checkbox."""

    tag = "Switch"

    # Change the default rendered element for the one passed as a child, merging their props and behavior.
    as_child: Optional[Var[bool]] = None

    # Whether the switch is checked by default
    default_checked: Optional[Var[bool]] = None

    # Whether the switch is checked
    checked: Optional[Var[bool]] = None

    # If true, prevent the user from interacting with the switch
    disabled: Optional[Var[bool]] = None

    # If true, the user must interact with the switch to submit the form
    required: Optional[Var[bool]] = None

    # The name of the switch (when submitting a form)
    name: Optional[Var[str]] = None

    # The value associated with the "on" position
    value: Optional[Var[str]] = None

    # Switch size "1" - "4"
    size: Optional[Var[LiteralSwitchSize]] = None

    # Variant of switch: "classic" | "surface" | "soft"
    variant: Optional[Var[Literal["classic", "surface", "soft"]]] = None

    # Override theme color for switch
    color_scheme: Optional[Var[LiteralAccentColor]] = None

    # Whether to render the switch with higher contrast color against background
    high_contrast: Optional[Var[bool]] = None

    # Override theme radius for switch: "none" | "small" | "full"
    radius: Optional[Var[Literal["none", "small", "full"]]] = None

    # Props to rename
    _rename_props = {"onChange": "onCheckedChange"}

    def get_event_triggers(self) -> Dict[str, Any]:
        """Get the event triggers that pass the component's value to the handler.

        Returns:
            A dict mapping the event trigger name to the argspec passed to the handler.
        """
        return {
            **super().get_event_triggers(),
            EventTriggers.ON_CHANGE: lambda checked: [checked],
        }


switch = Switch.create
