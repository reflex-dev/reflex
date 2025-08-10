"""Interactive components provided by @radix-ui/themes."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Literal

from reflex.components.component import Component
from reflex.components.core.breakpoints import Responsive
from reflex.components.radix.themes.base import LiteralAccentColor, RadixThemesComponent
from reflex.event import EventHandler, passthrough_event_spec
from reflex.utils.types import typehint_issubclass
from reflex.vars.base import Var

on_value_event_spec = (
    passthrough_event_spec(list[int | float]),
    passthrough_event_spec(list[int]),
    passthrough_event_spec(list[float]),
)


class Slider(RadixThemesComponent):
    """Provides user selection from a range of values."""

    tag = "Slider"

    # Change the default rendered element for the one passed as a child, merging their props and behavior.
    as_child: Var[bool]

    # Button size "1" - "3"
    size: Var[Responsive[Literal["1", "2", "3"]]]

    # Variant of button
    variant: Var[Literal["classic", "surface", "soft"]]

    # Override theme color for button
    color_scheme: Var[LiteralAccentColor]

    # Whether to render the button with higher contrast color against background
    high_contrast: Var[bool]

    # Override theme radius for button: "none" | "small" | "full"
    radius: Var[Literal["none", "small", "full"]]

    # The value of the slider when initially rendered. Use when you do not need to control the state of the slider.
    default_value: Var[Sequence[float | int] | float | int]

    # The controlled value of the slider. Must be used in conjunction with onValueChange.
    value: Var[Sequence[float | int]]

    # The name of the slider. Submitted with its owning form as part of a name/value pair.
    name: Var[str]

    # The width of the slider.
    width: Var[str | None] = Var.create("100%")

    # The minimum value of the slider.
    min: Var[float | int]

    # The maximum value of the slider.
    max: Var[float | int]

    # The step value of the slider.
    step: Var[float | int]

    # Whether the slider is disabled
    disabled: Var[bool]

    # The orientation of the slider.
    orientation: Var[Literal["horizontal", "vertical"]]

    # Props to rename
    _rename_props = {"onChange": "onValueChange"}

    # Fired when the value of the slider changes.
    on_change: EventHandler[on_value_event_spec]

    # Fired when a thumb is released after being dragged.
    on_value_commit: EventHandler[on_value_event_spec]

    @classmethod
    def create(
        cls,
        *children,
        **props,
    ) -> Component:
        """Create a Slider component.

        Args:
            *children: The children of the component.
            **props: The properties of the component.

        Returns:
            The component.
        """
        default_value = props.pop("default_value", [50])
        width = props.pop("width", "100%")

        if isinstance(default_value, Var):
            if typehint_issubclass(default_value._var_type, int | float):
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
