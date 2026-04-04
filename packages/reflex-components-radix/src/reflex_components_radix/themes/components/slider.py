"""Interactive components provided by @radix-ui/themes."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Literal

from reflex_base.components.component import Component, field
from reflex_base.event import EventHandler, passthrough_event_spec
from reflex_base.utils.types import typehint_issubclass
from reflex_base.vars.base import Var
from reflex_components_core.core.breakpoints import Responsive

from reflex_components_radix.themes.base import LiteralAccentColor, RadixThemesComponent

on_value_event_spec = (
    passthrough_event_spec(list[float]),
    passthrough_event_spec(list[int]),
)


class Slider(RadixThemesComponent):
    """Provides user selection from a range of values."""

    tag = "Slider"

    as_child: Var[bool] = field(
        doc="Change the default rendered element for the one passed as a child, merging their props and behavior."
    )

    size: Var[Responsive[Literal["1", "2", "3"]]] = field(doc='Button size "1" - "3"')

    variant: Var[Literal["classic", "surface", "soft"]] = field(doc="Variant of button")

    color_scheme: Var[LiteralAccentColor] = field(doc="Override theme color for button")

    high_contrast: Var[bool] = field(
        doc="Whether to render the button with higher contrast color against background"
    )

    radius: Var[Literal["none", "small", "full"]] = field(
        doc='Override theme radius for button: "none" | "small" | "full"'
    )

    default_value: Var[Sequence[float | int] | float | int] = field(
        doc="The value of the slider when initially rendered. Use when you do not need to control the state of the slider."
    )

    value: Var[Sequence[float | int]] = field(
        doc="The controlled value of the slider. Must be used in conjunction with onValueChange."
    )

    name: Var[str] = field(
        doc="The name of the slider. Submitted with its owning form as part of a name/value pair."
    )

    width: Var[str | None] = field(
        default=Var.create("100%"), doc="The width of the slider."
    )

    min: Var[float | int] = field(doc="The minimum value of the slider.")

    max: Var[float | int] = field(doc="The maximum value of the slider.")

    step: Var[float | int] = field(doc="The step value of the slider.")

    disabled: Var[bool] = field(doc="Whether the slider is disabled")

    orientation: Var[Literal["horizontal", "vertical"]] = field(
        doc="The orientation of the slider."
    )

    # Props to rename
    _rename_props = {"onChange": "onValueChange"}

    on_change: EventHandler[on_value_event_spec] = field(
        doc="Fired when the value of the slider changes."
    )

    on_value_commit: EventHandler[on_value_event_spec] = field(
        doc="Fired when a thumb is released after being dragged."
    )

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
        style.update({
            "width": width,
        })
        return super().create(*children, default_value=default_value, **props)


slider = Slider.create
