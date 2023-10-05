"""A heading component."""

from typing import Literal

from reflex.components.libs.chakra import ChakraComponent
from reflex.vars import Var


class Heading(ChakraComponent):
    """A page heading."""

    tag = "Heading"

    # Override the tag. The default tag is `<h2>`.
    as_: Var[str]

    # "4xl" | "3xl" | "2xl" | "xl" | "lg" | "md" | "sm" | "xs"
    size: Var[Literal["lg", "md", "sm", "xs", "2xl", "3xl", "4xl"]]
