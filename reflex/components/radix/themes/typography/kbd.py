"""Components for rendering heading.

https://www.radix-ui.com/themes/docs/theme/typography
"""
from __future__ import annotations

from reflex import el
from reflex.vars import Var

from ..base import (
    RadixThemesComponent,
)
from .base import (
    LiteralTextSize,
)


class Kbd(el.Kbd, RadixThemesComponent):
    """Represents keyboard input or a hotkey."""

    tag = "Kbd"

    # Text size: "1" - "9"
    size: Var[LiteralTextSize]
