"""A box component that can contain other components."""

from pynecone.components.libs.chakra import ChakraComponent
from pynecone.components.tags import Tag
from pynecone.var import Var


class Box(ChakraComponent):
    """A generic container component that can contain other components."""

    tag = "Box"

    # The type element to render. You can specify as an image, video, or any other HTML element such as iframe.
    element: Var[str]

    # The source of the content.
    src: Var[str]

    # The alt text of the content.
    alt: Var[str]

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
