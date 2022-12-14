"""A box component that can contain other components."""

from typing import Optional

from pynecone.components.libs.chakra import ChakraComponent
from pynecone.components.tags import Tag
from pynecone.var import Var
from pynecone import utils
from typing import Dict


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


class Html(Box):
    """Render the html.

    Returns:
        The code to render the  html component.
    """

    # The HTML to render.
    dangerouslySetInnerHTML: Var[Dict]

    @classmethod
    def create(cls, *children, **props):
        """Create a html component.

        Args:
            *children: The children of the component.
            **props: The props to pass to the component.

        Returns:
            The datable html.

        Raises:
            ValueError: If a pandas dataframe is passed in and columns are also provided.
        """
        # If children are not prvided, throw an error.
        if len(children) != 1:
            raise ValueError("Must provide children to the html component.")
        else:

            props["dangerouslySetInnerHTML"] = {"__html": children[0]}

        # Create the component.
        return super().create(**props)
