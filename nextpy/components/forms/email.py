"""An email input component."""

from nextpy.components.forms.input import Input
from nextpy.core.vars import Var


class Email(Input):
    """An email input component."""

    # The type of input.
    type_: Var[str] = "email"  # type: ignore
