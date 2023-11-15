"""A date input component."""

from nextpy.components.forms.input import Input
from nextpy.core.vars import Var


class DatePicker(Input):
    """A date input component."""

    # The type of input.
    type_: Var[str] = "date"  # type: ignore
