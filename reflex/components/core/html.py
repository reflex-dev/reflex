"""A html component."""

from typing import Dict

from reflex.components.el.elements.typography import Div
from reflex.vars.base import Var


class Html(Div):
    """Render the html.

    Returns:
        The code to render the html component.
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

        # Apply the default classname
        given_class_name = props.pop("class_name", [])
        if isinstance(given_class_name, str):
            given_class_name = [given_class_name]
        props["class_name"] = ["rx-Html", *given_class_name]

        # Create the component.
        return super().create(**props)


html = Html.create
