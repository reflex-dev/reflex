"""Interactive components provided by @radix-ui/themes."""
from typing import Any, Dict, Literal, Union

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

LiteralAvatarSize = Literal["1", "2", "3"]


class Tooltip(CommonMarginProps, RadixThemesComponent):

    tag = "Tooltip"

    # The content of the tooltip
    content: Component
