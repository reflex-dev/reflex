"""A box component that can contain other components."""

from pynecone.components.libs.chakra import ChakraComponent
from pynecone.components.tags import Tag
from pynecone.var import Var
from typing import Optional


class Box(ChakraComponent):
    """Renders a box component that can contain other components."""

    tag = "Box"

    # The type element to render. You can specify as an image, video, or any other HTML element such as iframe.
    element: Var[str]

    # The source of the content.
    src: Optional[str] = None

    # The alt text of the content.
    alt: Optional[str] = None

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
