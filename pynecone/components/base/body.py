"""Display the page body."""

from pynecone.components.component import Component
from pynecone.components.tags import Tag
from pynecone.var import Var


class Body(Component):
    """A body component."""

    def _render(self) -> Tag:
        return Tag(name="body")
