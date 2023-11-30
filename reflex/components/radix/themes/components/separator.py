"""Interactive components provided by @radix-ui/themes."""
from typing import Any, Dict, Literal

from reflex import el
from reflex.components.component import Component
from reflex.components.forms.debounce import DebounceInput
from reflex.constants import EventTriggers
from reflex.vars import Var

from ..base import (
    CommonMarginProps,
    LiteralAccentColor,
    LiteralRadius,
    LiteralSize,
    LiteralVariant,
    RadixThemesComponent,
)

LiteralButtonSize = Literal[1, 2, 3, 4]


class Seperator(CommonMarginProps, RadixThemesComponent):
    """Trigger an action or event, such as submitting a form or displaying a dialog."""

    tag = "Seperator"

    # The size of the select: "1" | "2" | "3" 
    size: Var[Literal[1, 2, 3, 4]]

    # The color of the select
    color: Var[LiteralAccentColor]

    # The orientation of the separator.
    orientation: Var[Literal["horizontal", "vertical"]]

    # When true, signifies that it is purely visual, carries no semantic meaning, and ensures it is not present in the accessibility tree.
    decorative: Var[bool]