"""A datetime-local input component."""

from reflex.components.forms.input import Input
from reflex.vars import Var


class DateTimePicker(Input):
    """A datetime-local input component."""

    # The type of input.
    type_: Var[str] = "datetime-local"  # type: ignore
