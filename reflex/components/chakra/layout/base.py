from reflex.components.component import Component


class ChakraLayoutComponent(Component):
    """A component that wraps a Chakra component."""

    library = "@chakra-ui/layout@2.3.1"

    def _get_style(self) -> dict:
        """Get the style for the component.

        Returns:
            The dictionary of the component style as value and the style notation as key.
        """
        return {"sx": self.style}