"""A date input component."""

from pynecone.components.forms.input import Input
from pynecone.vars import Var


class DatePicker(Input):
    """A date input component."""

    # The type of input.
    type_: Var[str] = "date"  # type: ignore
