"""The Radix slider component."""
from typing import List, Optional

from reflex.components.component import Component


class SliderComponent(Component):
    """A component that wraps a Radix slider component."""

    library = "@radix-ui/react-slider"

    is_default = False  # Use named exports.

    # Whether to use a child.
    as_child: Optional[bool]


class SliderRoot(SliderComponent):
    """Radix slider root."""

    tag = "Root"
    alias = "SliderRoot"

    # The default value of the slider.
    default_value: Optional[List[int]]

    # The current value of the slider.
    value: Optional[List[int]]

    # Whether the slider is disabled.
    disabled: Optional[bool]

    # The name of the slider.
    name: Optional[str]

    # The minimum value of the slider.
    min: Optional[int]

    # The maximum value of the slider.
    max: Optional[int]

    # The step of the slider.
    step: Optional[int]

    # The minimum steps between thumbs.
    min_steps_between_thumbs: Optional[int]


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
