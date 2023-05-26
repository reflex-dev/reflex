"""An email input component."""

from pynecone.components.forms.input import Input
from pynecone.vars import Var


class Email(Input):
    """An email input component."""

    # The type of input.
    type_: Var[str] = "email"  # type: ignore
