"""A reflexive container component."""
from typing import List, Optional, Union

from reflex.components.chakra import ChakraComponent
from reflex.vars import Var


class Flex(ChakraComponent):
    """A reflexive container component."""

    tag: str = "Flex"

    # How to align items in the flex.
    align: Optional[Var[str]] = None

    # Shorthand for flexBasis style prop
    basis: Optional[Var[str]] = None

    # Shorthand for flexDirection style prop
    direction: Optional[Var[Union[str, List[str]]]] = None

    # Shorthand for flexGrow style prop
    grow: Optional[Var[str]] = None

    # The way to justify the items.
    justify: Optional[Var[str]] = None

    # Shorthand for flexWrap style prop
    wrap: Optional[Var[Union[str, List[str]]]] = None

    # Shorthand for flexShrink style prop
    shrink: Optional[Var[str]] = None
