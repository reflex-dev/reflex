"""A box component that can contain other components."""

from pynecone.components.libs.chakra import ChakraComponent
from pynecone.components.tags import Tag
from pynecone.var import Var


class Box(ChakraComponent):
    """Renders a box component that can contain other components."""

    tag = "Box"

    # The element to render.
    element: Var[str]

    def _render(self) -> Tag:
        return (
            super()
            ._render()
            .add_props(
                **{
                    "as": self.element,
                }
            )
        )
