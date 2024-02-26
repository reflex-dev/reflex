"""A password input component."""

from reflex.components.chakra.forms.input import Input
from reflex.vars import Var


class Password(Input):
    """A password input component."""

    # The type of input.
    type_: Var[str] = "password"  # type: ignore
