"""A time input component."""

from reflex.components.chakra.forms.input import Input
from reflex.vars import Var


class TimePicker(Input):
    """A time input component."""

    # The type of input.
    type_: Var[str] = "time"  # type: ignore
