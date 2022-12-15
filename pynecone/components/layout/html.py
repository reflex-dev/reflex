"""A html component."""

from typing import Optional
from pynecone.components.libs.chakra import ChakraComponent
from pynecone.components.tags import Tag
from pynecone.components.layout.box import Box
from pynecone.var import Var
from pynecone import utils
from typing import Dict


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
