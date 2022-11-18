"""Container to stack elements with spacing."""

from pynecone.components.libs.chakra import ChakraComponent
from pynecone.var import Var


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
    thickness: Var[int]

    # The color name of the progress track. Use a color key in the theme object
    track_color: Var[str]

    # Current progress (must be between min/max).
    value: Var[int]

    # The desired valueText to use in place of the value.
    value_text: Var[str]


class CircularProgressLabel(ChakraComponent):
    """Label of CircularProcess."""

    tag = "CircularProgressLabel"
