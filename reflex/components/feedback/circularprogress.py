"""Container to stack elements with spacing."""
from typing import Union

from reflex.components.component import Component
from reflex.components.libs.chakra import ChakraComponent
from reflex.vars import Var


class CircularProgress(ChakraComponent):
    """The CircularProgress component is used to indicate the progress for determinate and indeterminate processes."""

    tag = "CircularProgress"

    # If true, the cap of the progress indicator will be rounded.
    cap_is_round: Var[bool]

    # If true, the progress will be indeterminate and the value prop will be ignored
    is_indeterminate: Var[bool]

    # Maximum value defining 100% progress made (must be higher than 'min')
    max_: Var[int]

    # Minimum value defining 'no progress' (must be lower than 'max')
    min_: Var[int]

    # This defines the stroke width of the svg circle.
    thickness: Var[Union[str, int]]

    # The color name of the progress track. Use a color key in the theme object
    track_color: Var[str]

    # Current progress (must be between min/max).
    value: Var[int]

    # The desired valueText to use in place of the value.
    value_text: Var[str]

    # The color name of the progress bar
    color: Var[str]

    # The size of the circular progress
    size: Var[str]

    @classmethod
    def create(cls, *children, label=None, **props) -> Component:
        """Create a circular progress component.

        Args:
            *children: the children of the component.
            label: A label to add in the circular progress. Defaults to None.
            **props: the props of the component.

        Returns:
            The circular progress component.
        """
        if len(children) == 0:
            children = []

            if label is not None:
                children.append(CircularProgressLabel.create(label))
        return super().create(*children, **props)


class CircularProgressLabel(ChakraComponent):
    """Label of CircularProcess."""

    tag = "CircularProgressLabel"
