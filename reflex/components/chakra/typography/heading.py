"""A heading component."""
from typing import Optional

from reflex.components.chakra import ChakraComponent, LiteralHeadingSize
from reflex.vars import Var


class Heading(ChakraComponent):
    """A page heading."""

    tag = "Heading"

    # Override the tag. The default tag is `<h2>`.
    as_: Optional[Var[str]] = None

    # "4xl" | "3xl" | "2xl" | "xl" | "lg" | "md" | "sm" | "xs"
    size: Optional[Var[LiteralHeadingSize]] = None
