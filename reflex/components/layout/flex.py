"""A reflexive container component."""

from reflex.components.libs.chakra import ChakraComponent
from reflex.vars import Var
from typing import Union


class Flex(ChakraComponent):
    """A reflexive container component."""

    tag = "Flex"

    # How to align items in the flex.
    align: Var[str]

    # Shorthand for flexBasis style prop
    basis: Var[str]

    # Shorthand for flexDirection style prop
    direction: Var[Union[str, list]]

    # Shorthand for flexGrow style prop
    grow: Var[str]

    # The way to justify the items.
    justify: Var[str]

    # Shorthand for flexWrap style prop
    wrap: Var[Union[str, list]]

    # Shorthand for flexShrink style prop
    shrink: Var[str]
