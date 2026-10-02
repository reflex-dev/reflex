"""A html component."""

from reflex_base.components.component import field
from reflex_base.vars.base import Var

from reflex_components_core.el.elements.typography import Div


class Html(Div):
    """Render the html.

    Returns:
        The code to render the html component.
    """

    dangerouslySetInnerHTML: Var[dict[str, str]] = field(doc="The HTML to render.")  # noqa: N815

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
            msg = "Must provide children to the html component."
            raise ValueError(msg)
        props["dangerouslySetInnerHTML"] = {"__html": children[0]}

        # Apply the default classname
        given_class_name = props.pop("class_name", [])
        if isinstance(given_class_name, str):
            given_class_name = [given_class_name]
        props["class_name"] = ["rx-Html", *given_class_name]

        # Create the component.
        return super().create(**props)


html = Html.create
