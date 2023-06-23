"""An icon button component."""

from reflex.components.typography.text import Text
from reflex.vars import Var


class IconButton(Text):
    """A button with an icon."""

    tag = "IconButton"

    # The type of button.
    type: Var[str]

    #  A label that describes the button
    aria_label: Var[str]

    # The icon to be used in the button.
    icon: Var[str]

    # If true, the button will be styled in its active state.
    is_active: Var[bool]

    # If true, the button will be disabled.
    is_disabled: Var[bool]

    # If true, the button will show a spinner.
    is_loading: Var[bool]

    # If true, the button will be perfectly round. Else, it'll be slightly round
    is_round: Var[bool]

    # Replace the spinner component when isLoading is set to true
    spinner: Var[str]
