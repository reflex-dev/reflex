"""A html component."""

from typing import Any

from pynecone.components.layout.box import Box


class Html(Box):
    """Render the html.

    Returns:
        The code to render the html component.
    """

    # The HTML to render.
    dangerouslySetInnerHTML: Any

    @classmethod
    def create(cls, *children, **props):
        """Create an html component.

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
            raise ValueError("Must provide a single child to the html component.")
        else:
            child = children[0]
            wrapped_child = child  # Initialize with the child as is

            # Check for header tags and wrap them accordingly
            if child.startswith("<h1>") and child.endswith("</h1>"):
                wrapped_child = f"<h1>{child[4:-5]}</h1>"
            elif child.startswith("<h2>") and child.endswith("</h2>"):
                wrapped_child = f"<h2>{child[4:-5]}</h2>"
            elif child.startswith("<h3>") and child.endswith("</h3>"):
                wrapped_child = f"<h3>{child[4:-5]}</h3>"
            elif child.startswith("<h4>") and child.endswith("</h4>"):
                wrapped_child = f"<h4>{child[4:-5]}</h4>"
            elif child.startswith("<h5>") and child.endswith("</h5>"):
                wrapped_child = f"<h5>{child[4:-5]}</h5>"
            elif child.startswith("<h6>") and child.endswith("</h6>"):
                wrapped_child = f"<h6>{child[4:-5]}</h6>"
            # Add more conditions for other header tags if needed

            # Check for bold tag and wrap accordingly
            elif child.startswith("<strong>") and child.endswith("</strong>"):
                wrapped_child = f"<strong>{child[8:-9]}</strong>"

            # Check for italic tag and wrap accordingly
            elif child.startswith("<em>") and child.endswith("</em>"):
                wrapped_child = f"<em>{child[4:-5]}</em>"

            props["dangerouslySetInnerHTML"] = {"__html": wrapped_child}

        # Create the component.
        return super().create(**props)
