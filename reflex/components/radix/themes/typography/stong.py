"""Components for rendering heading.

https://www.radix-ui.com/themes/docs/theme/typography
"""
from __future__ import annotations

from typing import Literal

from reflex import el
from reflex.vars import Var

from ..base import (
    CommonMarginProps,
    LiteralAccentColor,
    LiteralVariant,
    RadixThemesComponent,
)

from .base import (
    LiteralTextWeight,
    LiteralTextAlign,
    LiteralTextSize,
    LiteralTextTrim,

)



class Strong(el.Strong, CommonMarginProps, RadixThemesComponent):
    """Marks text to signify strong importance."""

    tag = "Strong"
