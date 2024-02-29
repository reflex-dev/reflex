"""An icon button component."""
from typing import Optional

from reflex.components.chakra.typography.text import Text
from reflex.components.component import Component
from reflex.vars import Var


class IconButton(Text):
    """A button with an icon."""

    tag = "IconButton"
    library = "@chakra-ui/button@2.1.0"

    # The type of button.
    type: Optional[Var[str]] = None

    #  A label that describes the button
    aria_label: Optional[Var[str]] = None

    # The icon to be used in the button.
    icon: Optional[Component]

    # If true, the button will be styled in its active state.
    is_active: Optional[Var[bool]] = None

    # If true, the button will be disabled.
    is_disabled: Optional[Var[bool]] = None

    # If true, the button will show a spinner.
    is_loading: Optional[Var[bool]] = None

    # If true, the button will be perfectly round. Else, it'll be slightly round
    is_round: Optional[Var[bool]] = None

    # Replace the spinner component when isLoading is set to true
    spinner: Optional[Var[str]] = None
