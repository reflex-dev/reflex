"""Chakra Card component."""

from typing import Optional

from pynecone.components.component import Component
from pynecone.components.libs.chakra import ChakraComponent
from pynecone.vars import Var


class Chead(ChakraComponent):
    """The wrapper that contains a card's header."""

    tag = "CardHeader"


class Cbody(ChakraComponent):
    """The wrapper that houses the card's main content."""

    tag = "CardBody"


class Cfoot(ChakraComponent):
    """The footer that houses the card actions."""

    tag = "CardFooter"


class Card(ChakraComponent):
    """The parent wrapper that provides context for its children."""

    tag = "Card"

    # [required] The flex alignment of the card
    align: Var[str]

    # [required] The flex direction of the card
    direction: Var[str]

    # [required] The flex distribution of the card
    justify: Var[str]

    # The visual color appearance of the component.
    # options: "whiteAlpha" | "blackAlpha" | "gray" | "red" | "orange" | "yellow" |
    #  "green" | "teal" | "blue" | "cyan" | "purple" | "pink" | "linkedin" |
    #  "facebook" | "messenger" | "whatsapp" | "twitter" | "telegram"
    # default: "gray"
    color_scheme: Var[str]

    # The size of the Card
    # options: "sm" | "md" | "lg"
    # default: "md"
    size: Var[str]

    # The variant of the Card
    # options: "elevated" | "outline" | "filled" | "unstyled"
    # default: "elevated"
    variant: Var[str]

    @classmethod
    def create(
        cls,
        body: Component,
        *,
        header: Optional[Component] = None,
        footer: Optional[Component] = None,
        **props
    ) -> Component:
        """Creates a Chakra Card with a body and optionally header and/or footer, and returns it.

        Args:
            body (Component): The main content of the Card that will be created.
            header (Optional[Component]): Should be a pc.Chead instance.
            footer (Optional[Component]): Should be a pc.Cfoot instance.
            props: The properties to be passed to the component.

        Returns:
            The `create()` method returns a Card object.
        """
        children = [x for x in (header, body, footer) if x is not None]
        return super().create(*children, **props)
