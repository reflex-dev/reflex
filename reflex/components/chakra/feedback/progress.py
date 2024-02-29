"""Container to stack elements with spacing."""
from typing import Optional, Union

from reflex.components.chakra import ChakraComponent
from reflex.vars import Var


class Progress(ChakraComponent):
    """A bar to display progress."""

    tag = "Progress"

    # If true, the progress bar will show stripe
    has_stripe: Optional[Var[bool]] = None

    # If true, and has_stripe is true, the stripes will be animated
    is_animated: Optional[Var[bool]] = None

    # If true, the progress will be indeterminate and the value prop will be ignored
    is_indeterminate: Optional[Var[bool]] = None

    # The maximum value of the progress
    max_: Optional[Var[int]] = None

    # The minimum value of the progress
    min_: Optional[Var[int]] = None

    # The value of the progress indicator. If undefined the progress bar will be in indeterminate state
    value: Optional[Var[Union[int, float]]] = None

    # The color scheme of the progress bar.
    color_scheme: Optional[Var[str]] = None
