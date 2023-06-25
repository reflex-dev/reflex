"""A heading component."""

from reflex.components.libs.chakra import ChakraComponent
from reflex.vars import Var


class Heading(ChakraComponent):
    """A page heading."""

    tag = "Heading"

    # "4xl" | "3xl" | "2xl" | "xl" | "lg" | "md" | "sm" | "xs"
    size: Var[str]
