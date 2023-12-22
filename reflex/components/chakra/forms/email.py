"""An email input component."""

from reflex.components.chakra.forms.input import Input
from reflex.vars import Var


class Email(Input):
    """An email input component."""

    # The type of input.
    type_: Var[str] = "email"  # type: ignore
