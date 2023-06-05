"""A datetime-local input component."""

from pynecone.components.forms.input import Input
from pynecone.vars import Var


class DateTimePicker(Input):
    """A datetime-local input component."""

    # The type of input.
    type_: Var[str] = "datetime-local"  # type: ignore
