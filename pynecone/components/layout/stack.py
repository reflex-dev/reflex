"""Container to stack elements with spacing."""

from pynecone.components.libs.chakra import ChakraComponent
from pynecone.var import Var


class Stack(ChakraComponent):
    """Display a square box."""

    tag = "Stack"

    # Shorthand for alignItems style prop
    align_items: Var[str]

    # The direction to stack the items.
    direction: Var[str]

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
    """The HStack component is a component which is only facing the horizontal direction. Additionally you can add a divider and horizontal spacing between the items."""

    tag = "HStack"


class Vstack(Stack):
    """The VStack component is a component which is only facing the vertical direction. Additionally you can add a divider and vertical spacing between the items."""

    tag = "VStack"
