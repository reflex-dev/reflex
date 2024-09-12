"""Interactive components provided by @radix-ui/themes."""

from typing import List, Literal, Optional, Union

from reflex.components.component import Component
from reflex.components.core.breakpoints import Responsive
from reflex.event import EventHandler
from reflex.ivars.base import ImmutableVar

from ..base import (
    LiteralAccentColor,
    RadixThemesComponent,
)


class Slider(RadixThemesComponent):
    """Provides user selection from a range of values."""

    tag = "Slider"

    # Change the default rendered element for the one passed as a child, merging their props and behavior.
    as_child: ImmutableVar[bool]

    # Button size "1" - "3"
    size: ImmutableVar[Responsive[Literal["1", "2", "3"]]]

    # Variant of button
    variant: ImmutableVar[Literal["classic", "surface", "soft"]]

    # Override theme color for button
    color_scheme: ImmutableVar[LiteralAccentColor]

    # Whether to render the button with higher contrast color against background
    high_contrast: ImmutableVar[bool]

    # Override theme radius for button: "none" | "small" | "full"
    radius: ImmutableVar[Literal["none", "small", "full"]]

    # The value of the slider when initially rendered. Use when you do not need to control the state of the slider.
    default_value: ImmutableVar[Union[List[Union[float, int]], float, int]]

    # The controlled value of the slider. Must be used in conjunction with onValueChange.
    value: ImmutableVar[List[Union[float, int]]]

    # The name of the slider. Submitted with its owning form as part of a name/value pair.
    name: ImmutableVar[str]

    # The minimum value of the slider.
    min: ImmutableVar[Union[float, int]]

    # The maximum value of the slider.
    max: ImmutableVar[Union[float, int]]

    # The step value of the slider.
    step: ImmutableVar[Union[float, int]]

    # Whether the slider is disabled
    disabled: ImmutableVar[bool]

    # The orientation of the slider.
    orientation: ImmutableVar[Literal["horizontal", "vertical"]]

    # Props to rename
    _rename_props = {"onChange": "onValueChange"}

    # Fired when the value of the slider changes.
    on_change: EventHandler[lambda e0: [e0]]

    # Fired when a thumb is released after being dragged.
    on_value_commit: EventHandler[lambda e0: [e0]]

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

        if isinstance(default_value, ImmutableVar):
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
