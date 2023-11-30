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


class HoverCardRoot(CommonMarginProps, RadixThemesComponent):
    """Trigger an action or event, such as submitting a form or displaying a dialog."""

    tag = "HoverCard.Root"


class HoverCardTrigger(CommonMarginProps, RadixThemesComponent):
    """Trigger an action or event, such as submitting a form or displaying a dialog."""

    tag = "HoverCard.Trigger"

class HoverCardContent(el.Div, CommonMarginProps, RadixThemesComponent):
    """Trigger an action or event, such as submitting a form or displaying a dialog."""

    tag = "HoverCard.Content"
