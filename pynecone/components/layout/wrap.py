"""Container to stack elements with spacing."""

from pynecone.components.libs.chakra import ChakraComponent


class Wrap(ChakraComponent):
    """Layout component used to add space between elements and wraps automatically if there isn't enough space."""

    tag = "Wrap"


class WrapItem(ChakraComponent):
    """Item of the Wrap component."""

    tag = "WrapItem"
