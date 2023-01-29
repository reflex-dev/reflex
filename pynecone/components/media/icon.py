"""An image component."""

from pynecone.components.component import Component


class ChakraIconComponent(Component):
    """A component that wraps a Chakra icon component."""

    library = "@chakra-ui/icons"


class Icon(ChakraIconComponent):
    """An image icon."""

    tag = "None"

    def __init__(self, *args, **kwargs):
        """Initialize the Icon component.

        Run some additional checks on Icon component.

        Args:
            args: The positional arguments
            kwargs: The keyword arguments

        Raises:
            AttributeError: The errors tied to bad usage of the Icon component.
        """
        if "tag" not in kwargs.keys():
            raise AttributeError("Missing 'tag' keyword-argument for Icon")
        if len(kwargs.get("children", [])) == 0:
            raise AttributeError(
                "Passing children to Icon component is not allowed: remove positional arguments to fix"
            )

        super().__init__(*args, **kwargs)
