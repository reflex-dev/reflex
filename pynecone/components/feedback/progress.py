"""Container to stack elements with spacing."""

from pynecone.components.libs.chakra import ChakraComponent
from pynecone.var import Var


class Progress(ChakraComponent):
    """A bar to display progress."""

    tag = "Progress"

    # If true, the progress bar will show stripe
    has_stripe: Var[bool]

    # If true, and hasStripe is true, the stripes will be animated
    is_animated: Var[bool]

    # If true, the progress will be indeterminate and the value prop will be ignored
    is_indeterminate: Var[bool]

    # The maximum value of the progress
    max_: Var[int]

    # The minimum value of the progress
    min_: Var[int]

    # The value of the progress indicator. If undefined the progress bar will be in indeterminate state
    value: Var[int]

    # The color scheme of the progress bar.
    color_scheme: Var[str]
