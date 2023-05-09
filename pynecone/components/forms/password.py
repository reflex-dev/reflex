"""A password input component."""

from pynecone.components.forms.input import Input
from pynecone.vars import Var


class Password(Input):
    """A password input component."""

    # The type of input.
    type_: Var[str] = "password"  # type: ignore
