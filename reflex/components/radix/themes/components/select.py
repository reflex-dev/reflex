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


class SelectRoot(CommonMarginProps, RadixThemesComponent):
    """Trigger an action or event, such as submitting a form or displaying a dialog."""

    tag = "Select.Root"

    # The size of the select: "1" | "2" | "3" 
    size: Var[Literal[1, 2, 3]]

class SelectTrigger(CommonMarginProps, RadixThemesComponent):
    """Trigger an action or event, such as submitting a form or displaying a dialog."""

    tag = "Select.Trigger"

    # Variant of the select trigger
    variant: Var[Literal["classic", "surface", "soft", "ghost"]]

    # The color of the select trigger
    color: Var[LiteralAccentColor]

    # The radius of the select trigger
    radius: Var[LiteralRadius]

class SelectContent(CommonMarginProps, RadixThemesComponent):
    """Trigger an action or event, such as submitting a form or displaying a dialog."""

    tag = "Select.Content"

    # The variant of the select content
    variant: Var[Literal["solid", "soft"]]

    # The color of the select content
    color: Var[LiteralAccentColor]

    # Whether to render the select content with higher contrast color against background
    high_contrast: Var[bool]

class SelectGroup(CommonMarginProps, RadixThemesComponent):
    """Trigger an action or event, such as submitting a form or displaying a dialog."""

    tag = "Select.Group"

class SelectItem(CommonMarginProps, RadixThemesComponent):
    """Trigger an action or event, such as submitting a form or displaying a dialog."""

    tag = "Select.Item"

class SelectLabel(CommonMarginProps, RadixThemesComponent):
    """Trigger an action or event, such as submitting a form or displaying a dialog."""

    tag = "Select.Label"

class SelectSeparator(CommonMarginProps, RadixThemesComponent):
    """Trigger an action or event, such as submitting a form or displaying a dialog."""

    tag = "Select.Separator"