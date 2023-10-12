"""Components that are based on Chakra-UI."""

from typing import Literal

from reflex.base import Base
from reflex.components.component import Component
from reflex.vars import Var


class ChakraComponent(Component):
    """A component that wraps a Chakra component."""

    library = "@chakra-ui/react"


class ChakraComponentColorSchemeMixin(Base):
    """A Chakra component mixin with color_scheme prop."""

    # Built in color scheme for ease of use.
    # Options:
    # "whiteAlpha" | "blackAlpha" | "gray" | "red" | "orange" | "yellow" | "green" | "teal" | "blue" | "cyan"
    # | "purple" | "pink" | "linkedin" | "facebook" | "messenger" | "whatsapp" | "twitter" | "telegram"
    color_scheme: Var[
        Literal[
            "gray",
            "red",
            "orange",
            "yellow",
            "green",
            "teal",
            "blue",
            "cyan",
            "purple",
            "pink",
            "whiteAlpha",
            "blackAlpha",
            "linkedin",
            "facebook",
            "messenger",
            "whatsapp",
            "twitter",
            "telegram",
        ]
    ]
