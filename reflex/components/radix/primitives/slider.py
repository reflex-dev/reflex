"""Radix slider components."""

from __future__ import annotations

from typing import Any, List, Literal, Tuple

from reflex.components.component import Component, ComponentNamespace
from reflex.components.radix.primitives.base import RadixPrimitiveComponentWithClassName
from reflex.event import EventHandler
from reflex.vars.base import Var

LiteralSliderOrientation = Literal["horizontal", "vertical"]
LiteralSliderDir = Literal["ltr", "rtl"]


class SliderComponent(RadixPrimitiveComponentWithClassName):
    """Base class for all @radix-ui/react-slider components."""

    library = "@radix-ui/react-slider@^1.1.2"


def on_value_event_spec(
    value: Var[List[int]],
) -> Tuple[Var[List[int]]]:
    """Event handler spec for the value event.

    Args:
        value: The value of the event.

    Returns:
        The event handler spec.
    """
    return (value,)  # type: ignore


class SliderRoot(SliderComponent):
    """The Slider component comtaining all slider parts."""

    tag = "Root"
    alias = "RadixSliderRoot"

    default_value: Var[List[int]]

    value: Var[List[int]]

    name: Var[str]

    disabled: Var[bool]

    orientation: Var[LiteralSliderOrientation]

    dir: Var[LiteralSliderDir]

    inverted: Var[bool]

    min: Var[int]

    max: Var[int]

    step: Var[int]

    min_steps_between_thumbs: Var[int]

    # Fired when the value of a thumb changes.
    on_value_change: EventHandler[on_value_event_spec]

    # Fired when a thumb is released.
    on_value_commit: EventHandler[on_value_event_spec]

    def add_style(self) -> dict[str, Any] | None:
        """Add style to the component.

        Returns:
            The style of the component.
        """
        return {
            "position": "relative",
            "display": "flex",
            "align_items": "center",
            "user_select": "none",
            "touch_action": "none",
            "width": "200px",
            "height": "20px",
            "&[data-orientation='vertical']": {
                "flex_direction": "column",
                "width": "20px",
                "height": "100px",
            },
        }


class SliderTrack(SliderComponent):
    """A Slider Track component."""

    tag = "Track"
    alias = "RadixSliderTrack"

    def add_style(self) -> dict[str, Any] | None:
        """Add style to the component.

        Returns:
            The style of the component.
        """
        return {
            "position": "relative",
            "flex_grow": "1",
            "background_color": "black",
            "border_radius": "9999px",
            "height": "3px",
            "&[data-orientation='vertical']": {"width": "3px"},
        }


class SliderRange(SliderComponent):
    """A SliderRange component."""

    tag = "Range"
    alias = "RadixSliderRange"

    def add_style(self) -> dict[str, Any] | None:
        """Add style to the component.

        Returns:
            The style of the component.
        """
        return {
            "position": "absolute",
            "background_color": "white",
            "height": "100%",
            "&[data-orientation='vertical']": {"width": "100%"},
        }


class SliderThumb(SliderComponent):
    """A SliderThumb component."""

    tag = "Thumb"
    alias = "RadixSliderThumb"

    def add_style(self) -> dict[str, Any] | None:
        """Add style to the component.

        Returns:
            The style of the component.
        """
        return {
            "display": "block",
            "width": "20px",
            "height": "20px",
            "background_color": "black",
            "box_shadow": "0 2px 10px black",
            "border_radius": "10px",
            "&:hover": {
                "background_color": "gray",
            },
            "&:focus": {
                "outline": "none",
                "box_shadow": "0 0 0 4px gray",
            },
        }


class Slider(ComponentNamespace):
    """High level API for slider."""

    root = staticmethod(SliderRoot.create)
    track = staticmethod(SliderTrack.create)
    range = staticmethod(SliderRange.create)
    thumb = staticmethod(SliderThumb.create)

    @staticmethod
    def __call__(**props) -> Component:
        """High level API for slider.

        Args:
            **props: The props of the slider.

        Returns:
            A slider component.
        """
        track = SliderTrack.create(SliderRange.create())
        # if default_value is not set, the thumbs will not render properly but the slider will still work
        if "default_value" in props:
            children = [
                track,
                *[SliderThumb.create() for _ in props.get("default_value", [])],
            ]
        else:
            children = [
                track,
                #     Foreach.create(props.get("value"), lambda e: SliderThumb.create()),  # foreach doesn't render Thumbs properly # noqa: ERA001
            ]

        return SliderRoot.create(*children, **props)


slider = Slider()
