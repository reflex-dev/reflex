"""A heading component."""

from pynecone.components.libs.chakra import ChakraComponent
from pynecone.var import Var


class Heading(ChakraComponent):
    """Heading composes Box so you can use all the style props and add responsive styles as well. It renders an h2 tag by default."""

    tag = "Heading"

    # "4xl" | "3xl" | "2xl" | "xl" | "lg" | "md" | "sm" | "xs"
    size: Var[str]
