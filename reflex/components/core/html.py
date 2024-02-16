"""A html component."""
from typing import Dict

from reflex.components.el.elements.typography import Div
from reflex.vars import Var


class Html(Div):
    """Render the html.

    Returns:
        The code to render the  html component.
    """

    # The HTML to render.
    dangerouslySetInnerHTML: Var[Dict[str, str]]

    @classmethod
    def create(cls, *children, **props):
        """Create a html component.

        Args:
            *children: The children of the component.
            **props: The props to pass to the component.

        Returns:
            The html component.

        Raises:
            ValueError: If children are not provided or more than one child is provided.
        """
        # If children are not provided, throw an error.
        if len(children) != 1:
            raise ValueError("Must provide children to the html component.")
        else:
            props["dangerouslySetInnerHTML"] = {"__html": children[0]}

        # Create the component.
        return super().create(**props)
