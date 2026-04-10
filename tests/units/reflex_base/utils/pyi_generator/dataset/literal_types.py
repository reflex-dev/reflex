"""Component with Literal type props.

This module tests:
- Literal type annotations on props
- Module-level Literal type aliases
- Var[Literal[...]] expansion (Var union with inner literal)
"""

from typing import Literal

from reflex_base.components.component import Component, field
from reflex_base.vars.base import Var

LiteralSize = Literal["sm", "md", "lg", "xl"]
LiteralVariant = Literal["solid", "outline", "ghost"]
LiteralOrientation = Literal["horizontal", "vertical"]


class ThemedComponent(Component):
    """A component with literal-typed props."""

    # The size of the component.
    size: Var[LiteralSize] = field(doc="Component size.")

    # The variant style.
    variant: Var[LiteralVariant] = field(doc="Visual variant.")

    orientation: Var[LiteralOrientation]

    # A direct Literal annotation without alias.
    color_scheme: Var[Literal["red", "green", "blue"]]
