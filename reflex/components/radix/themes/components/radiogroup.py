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


class RadioGroupRoot(CommonMarginProps, RadixThemesComponent):
    """Trigger an action or event, such as submitting a form or displaying a dialog."""

    tag = "RadioGroup.Root"

    # The size of the radio group: "1" | "2" | "3" 
    size: Var[Literal[1, 2, 3]]

    # The variant of the radio group
    variant: Var[Literal["classic", "surface", "soft"]]

    # The color of the radio group
    color: Var[LiteralAccentColor]

    # Whether to render the radio group with higher contrast color against background
    high_contrast: Var[bool]


class RadioGroupItem(CommonMarginProps, RadixThemesComponent):
    """Trigger an action or event, such as submitting a form or displaying a dialog."""

    tag = "RadioGroup.Item"
