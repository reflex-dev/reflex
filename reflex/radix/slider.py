"""The Radix slider component."""
from typing import List

from reflex.components import Component
from reflex.vars import Var


class SliderComponent(Component):
    """Base class for all slider components."""

    library = "@radix-ui/react-slider"

    is_default = False  # Use named exports.

    # Whether to use a child.
    as_child: Var[bool]


class SliderRoot(SliderComponent):
    """Radix slider root."""

    tag = "Root"
    alias = "SliderRoot"

    # The default value of the slider.
    default_value: Var[List[int]]

    # The current value of the slider.
    value: Var[List[int]]

    # Whether the slider is disabled.
    disabled: Var[bool]

    # The name of the slider.
    name: Var[str]

    # The minimum value of the slider.
    min: Var[int]

    # The maximum value of the slider.
    max: Var[int]

    # The step of the slider.
    step: Var[int]

    # The minimum steps between thumbs.
    min_steps_between_thumbs: Var[int]


class SliderTrack(SliderComponent):
    """Radix slider track."""

    tag = "Track"
    alias = "SliderTrack"


class SliderRange(SliderComponent):
    """Radix slider range."""

    tag = "Range"
    alias = "SliderRange"


class SliderThumb(SliderComponent):
    """Radix slider thumb."""

    tag = "Thumb"
    alias = "SliderThumb"
