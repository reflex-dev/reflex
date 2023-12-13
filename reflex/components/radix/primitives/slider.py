"""Radix slider components."""

from typing import Any, Dict, Literal

from reflex.components.component import Component
from reflex.components.radix.primitives.base import RadixPrimitiveComponent
from reflex.style import Style
from reflex.vars import Var

LiteralSliderOrientation = Literal["horizontal", "vertical"]
LiteralSliderDir = Literal["ltr", "rtl"]


class SliderComponent(RadixPrimitiveComponent):
    """Base class for all @radix-ui/react-slider components."""

    library = "@radix-ui/react-slider@^1.1.2"


class SliderRoot(SliderComponent):
    """The Slider component comtaining all slider parts."""

    tag = "Root"
    alias = "RadixSliderRoot"

    default_value: Var[list[int]]

    value: Var[int]

    name: Var[str]

    disabled: Var[bool]

    orientation: Var[LiteralSliderOrientation]

    dir: Var[LiteralSliderDir]

    inverted: Var[bool]

    min: Var[int]

    max: Var[int]

    step: Var[int]

    min_steps_between_thumbs: Var[int]

    def get_event_triggers(self) -> Dict[str, Any]:
        """Event triggers for radix slider primitive.

        Returns:
            The triggers for event supported by radix primitives.
        """
        return {
            **super().get_event_triggers(),
            "on_value_change": lambda e0: [e0],  # trigger for all change of a thumb
            "on_value_commit": lambda e0: [e0],  # trigger when thumb is released
        }

    def _apply_theme(self, theme: Component):
        self.style = Style(
            {
                "position": "relative",
                "display": "flex",
                "align-items": "center",
                "user-select": "none",
                "touch-action": "none",
                "width": "200px",
                "height": "20px",
                "&[data-orientation='vertical']": {
                    "flex-direction": "column",
                    "width": "20px",
                    "height": "100px",
                },
                **self.style,
            }
        )


class SliderTrack(SliderComponent):
    """A Slider Track component."""

    tag = "Track"
    alias = "RadixSliderTrack"

    def _apply_theme(self, theme: Component):
        self.style = Style(
            {
                "position": "relative",
                "flex-grow": "1",
                "background-color": "black",
                "border-radius": "9999px",
                "height": "3px",
                "&[data-orientation='vertical']": {
                    "width": "3px",
                },
                **self.style,
            }
        )


class SliderRange(SliderComponent):
    """A SliderRange component."""

    tag = "Range"
    alias = "RadixSliderRange"

    def _apply_theme(self, theme: Component):
        self.style = Style(
            {
                "position": "absolute",
                "background-color": "white",
                "&[data-orientation='vertical']": {
                    "width": "100%",
                },
                **self.style,
            }
        )


class SliderThumb(SliderComponent):
    """A SliderThumb component."""

    tag = "Thumb"
    alias = "RadixSliderThumb"

    def _apply_theme(self, theme: Component):
        self.style = Style(
            {
                "display": "block",
                "width": "20px",
                "height": "20px",
                "background-color": "black",
                "box-shadow": "0 2px 10px black",
                "border_radius": "10px",
                "&:hover": {
                    "background-color": "blue",
                },
                "&:focus": {
                    "outline": "none",
                    "box-shadow": "0 0 0 5px black",
                },
                **self.style,
            }
        )


slider_root = SliderRoot.create
slider_track = SliderTrack.create
slider_range = SliderRange.create
slider_thumb = SliderThumb.create


def slider(
    **props,
) -> Component:
    """High level API for slider.

    Args:
        **props: The props of the slider.

    Returns:
        A slider component.
    """
    # Support state vars ?
    children = [
        SliderTrack.create(SliderRange.create()),
        *[SliderThumb.create() for _ in props.get("default_value", [])],
    ]
    return slider_root(*children, **props)
