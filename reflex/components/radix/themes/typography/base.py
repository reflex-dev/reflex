"""Components for rendering text.

https://www.radix-ui.com/themes/docs/theme/typography
"""
from __future__ import annotations

from typing import Literal

from reflex.vars import Var

from ..base import (
    CommonMarginProps,
    LiteralAccentColor,
    LiteralVariant,
    RadixThemesComponent,
)

LiteralTextWeight = Literal["light", "regular", "medium", "bold"]
LiteralTextAlign = Literal["left", "center", "right"]
LiteralTextSize = Literal["1", "2", "3", "4", "5", "6", "7", "8", "9"]
LiteralTextTrim = Literal["normal", "start", "end", "both"]
