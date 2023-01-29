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
        """
        if "tag" not in kwargs.keys():
            raise AttributeError("Missing 'tag' keyword-argument for Icon")
        super().__init__(*args, **kwargs)
