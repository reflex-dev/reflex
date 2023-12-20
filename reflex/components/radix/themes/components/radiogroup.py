"""Interactive components provided by @radix-ui/themes."""
from typing import Any, Dict, Literal

from reflex.vars import Var

from ..base import (
    CommonMarginProps,
    LiteralAccentColor,
    RadixThemesComponent,
)


class RadioGroupRoot(CommonMarginProps, RadixThemesComponent):
    """Trigger an action or event, such as submitting a form or displaying a dialog."""

    tag = "RadioGroup.Root"

    # The size of the radio group: "1" | "2" | "3"
    size: Var[Literal["1", "2", "3"]]

    # The variant of the radio group
    variant: Var[Literal["classic", "surface", "soft"]]

    # The color of the radio group
    color: Var[LiteralAccentColor]

    # Whether to render the radio group with higher contrast color against background
    high_contrast: Var[bool]

    # The controlled value of the radio item to check. Should be used in conjunction with onValueChange.
    value: Var[str]

    # The initial value of checked radio item. Should be used in conjunction with onValueChange.
    default_value: Var[str]

    # Whether the radio group is disabled
    disabled: Var[bool]

    # Whether the radio group is required
    required: Var[bool]

    # The orientation of the component.
    orientation: Var[Literal["horizontal", "vertical"]]

    # When true, keyboard navigation will loop from last item to first, and vice versa.
    loop: Var[bool]

    def get_event_triggers(self) -> Dict[str, Any]:
        """Get the events triggers signatures for the component.

        Returns:
            The signatures of the event triggers.
        """
        return {
            **super().get_event_triggers(),
            "on_value_change": lambda e0: [e0],
        }


class RadioGroupItem(CommonMarginProps, RadixThemesComponent):
    """Trigger an action or event, such as submitting a form or displaying a dialog."""

    tag = "RadioGroup.Item"

    # The value of the radio item to check. Should be used in conjunction with onCheckedChange.
    value: Var[str]

    # When true, prevents the user from interacting with the radio item.
    disabled: Var[bool]

    # When true, indicates that the user must check the radio item before the owning form can be submitted.
    required: Var[bool]
