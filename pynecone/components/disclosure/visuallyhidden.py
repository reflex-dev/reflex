"""A component to display visually hidden text."""

from pynecone.components.libs.chakra import ChakraComponent


class VisuallyHidden(ChakraComponent):
    """A component that visually hides content while still allowing it to be read by screen readers."""

    tag = "VisuallyHidden"
