"""A password input component."""

from nextpy.components.forms.input import Input
from nextpy.core.vars import Var


class Password(Input):
    """A password input component."""

    # The type of input.
    type_: Var[str] = "password"  # type: ignore
