"""Container to stack elements with spacing."""

from typing import List, Union

from reflex.components.chakra import ChakraComponent, LiteralStackDirection
from reflex.vars import Var


class Stack(ChakraComponent):
    """Container to stack elements with spacing."""

    tag = "Stack"

    # Shorthand for alignItems style prop
    align_items: Var[str]

    # The direction to stack the items.
    direction: Var[Union[LiteralStackDirection, List[str]]]

    # If true the items will be stacked horizontally.
    is_inline: Var[bool]

    # Shorthand for justifyContent style prop
    justify_content: Var[str]

    # If true, the children will be wrapped in a Box, and the Box will take the spacing props
    should_wrap_children: Var[bool]

    # The space between each stack item
    spacing: Var[str]

    # Shorthand for flexWrap style prop
    wrap: Var[str]

    # Alignment of contents.
    justify: Var[str]


class Hstack(Stack):
    """Stack items horizontally."""

    tag = "HStack"


class Vstack(Stack):
    """Stack items vertically."""

    tag = "VStack"
