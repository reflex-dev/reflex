"""Interactive components provided by @radix-ui/themes."""
from typing import Any, Dict, List, Literal, Optional, Union

from reflex.components.component import Component
from reflex.constants import EventTriggers
from reflex.vars import Var

from ..base import (
    LiteralAccentColor,
    RadixThemesComponent,
)


class Slider(RadixThemesComponent):
    """Provides user selection from a range of values."""

    tag = "Slider"

    # Change the default rendered element for the one passed as a child, merging their props and behavior.
    as_child: Optional[Var[bool]] = None

    # Button size "1" - "3"
    size: Optional[Var[Literal["1", "2", "3"]]] = None

    # Variant of button
    variant: Optional[Var[Literal["classic", "surface", "soft"]]] = None

    # Override theme color for button
    color_scheme: Optional[Var[LiteralAccentColor]] = None

    # Whether to render the button with higher contrast color against background
    high_contrast: Optional[Var[bool]] = None

    # Override theme radius for button: "none" | "small" | "full"
    radius: Optional[Var[Literal["none", "small", "full"]]] = None

    # The value of the slider when initially rendered. Use when you do not need to control the state of the slider.
    default_value: Optional[Var[Union[List[Union[float, int]], float, int]]] = None

    # The controlled value of the slider. Must be used in conjunction with onValueChange.
    value: Optional[Var[List[Union[float, int]]]] = None

    # The name of the slider. Submitted with its owning form as part of a name/value pair.
    name: Optional[Var[str]] = None

    # The minimum value of the slider.
    min: Optional[Var[Union[float, int]]] = None

    # The maximum value of the slider.
    max: Optional[Var[Union[float, int]]] = None

    # The step value of the slider.
    step: Optional[Var[Union[float, int]]] = None

    # Whether the slider is disabled
    disabled: Optional[Var[bool]] = None

    # The orientation of the slider.
    orientation: Optional[Var[Literal["horizontal", "vertical"]]] = None

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

    @classmethod
    def create(
        cls,
        *children,
        width: Optional[str] = "100%",
        **props,
    ) -> Component:
        """Create a Slider component.

        Args:
            *children: The children of the component.
            width: The width of the slider.
            **props: The properties of the component.

        Returns:
            The component.
        """
        default_value = props.pop("default_value", [50])

        if isinstance(default_value, Var):
            if issubclass(default_value._var_type, (int, float)):
                default_value = [default_value]

        elif isinstance(default_value, (int, float)):
            default_value = [default_value]

        style = props.setdefault("style", {})
        style.update(
            {
                "width": width,
            }
        )
        return super().create(*children, default_value=default_value, **props)


slider = Slider.create
