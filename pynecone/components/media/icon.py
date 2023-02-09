"""An image component."""

import re

from pynecone.components.component import Component


class ChakraIconComponent(Component):
    """A component that wraps a Chakra icon component."""

    library = "@chakra-ui/icons"


class Icon(ChakraIconComponent):
    """An image icon."""

    tag = "None"

    @classmethod
    def create(cls, *children, **props):
        """Initialize the Icon component.

        Run some additional checks on Icon component.

        Args:
            children: The positional arguments
            props: The keyword arguments

        Raises:
            AttributeError: The errors tied to bad usage of the Icon component.

        Returns:
            The created component.
        """
        if children:
            raise AttributeError(
                f"Passing children to Icon component is not allowed: remove positional arguments {children} to fix"
            )
        if "tag" not in props.keys():
            raise AttributeError("Missing 'tag' keyword-argument for Icon")
        else:
            tag_keywords = [
                "add",
                "allowed",
                "arrow",
                "back",
                "circle",
                "clock",
                "close",
                "down",
                "forward",
                "handle",
                "icon",
                "left",
                "link",
                "off",
                "outline",
                "right",
                "sign",
                "two",
                "up",
            ]
            props["tag"] = props["tag"].title()
            for keyword in tag_keywords:
                props["tag"] = re.sub(keyword, keyword.title(), props["tag"])

        return super().create(*children, **props)
