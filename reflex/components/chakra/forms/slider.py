"""A slider component."""

from __future__ import annotations

from typing import Literal

from reflex.components.chakra import ChakraComponent, LiteralChakraDirection
from reflex.components.component import Component
from reflex.event import EventHandler
from reflex.vars import Var

LiteralLayout = Literal["horizontal", "vertical"]


class Slider(ChakraComponent):
    """The wrapper that provides context and functionality for all children."""

    tag = "Slider"

    # State var to bind the input.
    value: Var[int]

    # The color scheme.
    color_scheme: Var[str]

    # The placeholder text.
    default_value: Var[int]

    # The writing mode ("ltr" | "rtl")
    direction: Var[LiteralChakraDirection]

    # If false, the slider handle will not capture focus when value changes.
    focus_thumb_on_change: Var[bool]

    # If true, the slider will be disabled
    is_disabled: Var[bool]

    # If true, the slider will be in `read-only` state.
    is_read_only: Var[bool]

    # If true, the value will be incremented or decremented in reverse.
    is_reversed: Var[bool]

    # The minimum value of the slider.
    min_: Var[int]

    # The maximum value of the slider.
    max_: Var[int]

    # The step in which increments/decrements have to be made
    step: Var[int]

    # The minimum distance between slider thumbs. Useful for preventing the thumbs from being too close together.
    min_steps_between_thumbs: Var[int]

    # Oreintation of the slider vertical | horizontal.
    orientation: Var[LiteralLayout]

    # Minimum height of the slider.
    min_h: Var[str]

    # Minimum width of the slider.
    min_w: Var[str]

    # Maximum height of the slider.
    max_h: Var[str]

    # Maximum width of the slider.
    max_w: Var[str]

    # The name of the form field
    name: Var[str]

    # Fired when the value changes.
    on_change: EventHandler[lambda e0: [e0]]

    # Fired when the value starts changing.
    on_change_start: EventHandler[lambda e0: [e0]]

    # Fired when the value stops changing.
    on_change_end: EventHandler[lambda e0: [e0]]

    @classmethod
    def create(cls, *children, **props) -> Component:
        """Create a slider component.

        If no children are provided, a default slider will be created.

        Args:
            *children: The children of the component.
            **props: The properties of the component.

        Returns:
            The slider component.
        """
        if len(children) == 0:
            children = [
                SliderTrack.create(
                    SliderFilledTrack.create(),
                ),
                SliderThumb.create(),
            ]
        return super().create(*children, **props)


class SliderTrack(ChakraComponent):
    """The empty part of the slider that shows the track."""

    tag = "SliderTrack"


class SliderFilledTrack(ChakraComponent):
    """The filled part of the slider."""

    tag = "SliderFilledTrack"


class SliderThumb(ChakraComponent):
    """The handle that's used to change the slider value."""

    tag = "SliderThumb"

    # The size of the thumb.
    box_size: Var[str]


class SliderMark(ChakraComponent):
    """The label or mark that shows names for specific slider values."""

    tag = "SliderMark"
