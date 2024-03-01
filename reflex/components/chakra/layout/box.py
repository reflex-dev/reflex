"""A box component that can contain other components."""
from typing import Optional

from reflex.components.chakra import ChakraComponent
from reflex.components.tags import Tag
from reflex.vars import Var


class Box(ChakraComponent):
    """A generic container component that can contain other components."""

    tag: str = "Box"

    # The type element to render. You can specify an image, video, or any other HTML element such as iframe.
    element: Optional[Var[str]] = None

    # The source of the content.
    src: Optional[Var[str]] = None

    # The alt text of the content.
    alt: Optional[Var[str]] = None

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
