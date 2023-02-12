"""A password input component."""

from pynecone.var import Var
from pynecone.components.forms.input import Input


class Password(Input):
    """A password input component."""

    # The type of input.
    type_: Var[str] = "password"  # type: ignore
