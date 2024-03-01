"""Container to stack elements with spacing."""
from typing import List, Optional, Union

from reflex.components.chakra import ChakraComponent, LiteralStackDirection
from reflex.vars import Var


class Stack(ChakraComponent):
    """Container to stack elements with spacing."""

    tag: str = "Stack"

    # Shorthand for alignItems style prop
    align_items: Optional[Var[str]] = None

    # The direction to stack the items.
    direction: Optional[Var[Union[LiteralStackDirection, List[str]]]] = None

    # If true the items will be stacked horizontally.
    is_inline: Optional[Var[bool]] = None

    # Shorthand for justifyContent style prop
    justify_content: Optional[Var[str]] = None

    # If true, the children will be wrapped in a Box, and the Box will take the spacing props
    should_wrap_children: Optional[Var[bool]] = None

    # The space between each stack item
    spacing: Optional[Var[str]] = None

    # Shorthand for flexWrap style prop
    wrap: Optional[Var[str]] = None

    # Alignment of contents.
    justify: Optional[Var[str]] = None


class Hstack(Stack):
    """Stack items horizontally."""

    tag: str = "HStack"


class Vstack(Stack):
    """Stack items vertically."""

    tag: str = "VStack"
