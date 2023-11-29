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


class ScrollArea(CommonMarginProps, RadixThemesComponent):
    """Trigger an action or event, such as submitting a form or displaying a dialog."""

    tag = "ScrollArea"

    # The size of the radio group: "1" | "2" | "3" 
    size: Var[Literal[1, 2, 3]]

    # The radius of the radio group
    radius: Var[LiteralRadius]

    # The alignment of the scroll area
    scrollbars: Var[Literal["vertical", "horizontal", "both"]]

