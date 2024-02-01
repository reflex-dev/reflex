"""Interactive components provided by @radix-ui/themes."""
from typing import Any, Dict, List, Literal, Union

from reflex.constants import EventTriggers
from reflex.vars import Var

from ..base import (
    LiteralAccentColor,
    LiteralRadius,
    RadixThemesComponent,
)


class Slider(RadixThemesComponent):
    """Trigger an action or event, such as submitting a form or displaying a dialog."""

    tag = "Slider"

    # Change the default rendered element for the one passed as a child, merging their props and behavior.
    as_child: Var[bool]

    # Button size "1" - "3"
    size: Var[Literal["1", "2", "3"]]

    # Variant of button
    variant: Var[Literal["classic", "surface", "soft"]]

    # Override theme color for button
    color_scheme: Var[LiteralAccentColor]

    # Whether to render the button with higher contrast color against background
    high_contrast: Var[bool]

    # Override theme radius for button: "none" | "small" | "medium" | "large" | "full"
    radius: Var[LiteralRadius]

    # The value of the slider when initially rendered. Use when you do not need to control the state of the slider.
    default_value: Var[List[Union[float, int]]]

    # The controlled value of the slider. Must be used in conjunction with onValueChange.
    value: Var[List[Union[float, int]]]

    # The name of the slider. Submitted with its owning form as part of a name/value pair.
    name: Var[str]

    # The minimum value of the slider.
    min: Var[Union[float, int]]

    # The maximum value of the slider.
    max: Var[Union[float, int]]

    # The step value of the slider.
    step: Var[Union[float, int]]

    # Whether the slider is disabled
    disabled: Var[bool]

    # The orientation of the slider.
    orientation: Var[Literal["horizontal", "vertical"]]

    # Props to rename
    _rename_props = {"onChange": "onValueChange"}

    def get_event_triggers(self) -> Dict[str, Any]:
        """Get the events triggers signatures for the component.

        Returns:
            The signatures of the event triggers.
        """
        return {
            **super().get_event_triggers(),
            EventTriggers.ON_CHANGE: lambda e0: [e0],
            EventTriggers.ON_VALUE_COMMIT: lambda e0: [e0],
        }
