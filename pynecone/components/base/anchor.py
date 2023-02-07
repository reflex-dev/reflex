"""A anchor tag component."""

from pynecone.components.component import Component
from pynecone.var import Var


class Anchor(Component):
    """Anchor tag for hash link."""

    tag = "a"

    # The id.
    id: Var[str]

    # The name.
    name: Var[str]
