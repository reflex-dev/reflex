"""Container to stack elements with spacing."""
from typing import Optional, Union

from reflex.components.chakra import ChakraComponent
from reflex.components.component import Component
from reflex.vars import Var


class CircularProgress(ChakraComponent):
    """The CircularProgress component is used to indicate the progress for determinate and indeterminate processes."""

    tag = "CircularProgress"

    # If true, the cap of the progress indicator will be rounded.
    cap_is_round: Optional[Var[bool]] = None

    # If true, the progress will be indeterminate and the value prop will be ignored
    is_indeterminate: Optional[Var[bool]] = None

    # Maximum value defining 100% progress made (must be higher than 'min')
    max_: Optional[Var[int]] = None

    # Minimum value defining 'no progress' (must be lower than 'max')
    min_: Optional[Var[int]] = None

    # This defines the stroke width of the svg circle.
    thickness: Optional[Var[Union[str, int]]] = None

    # The color name of the progress track. Use a color key in the theme object
    track_color: Optional[Var[str]] = None

    # Current progress (must be between min/max).
    value: Optional[Var[int]] = None

    # The desired valueText to use in place of the value.
    value_text: Optional[Var[str]] = None

    # The color name of the progress bar
    color: Optional[Var[str]] = None

    # The size of the circular progress
    size: Optional[Var[str]] = None

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
