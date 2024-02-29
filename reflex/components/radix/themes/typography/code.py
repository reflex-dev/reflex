"""Components for rendering heading.
from typing import Optional
https://www.radix-ui.com/themes/docs/theme/typography.
"""
from __future__ import annotations

from typing import Optional

from reflex import el
from reflex.vars import Var

from ..base import (
    LiteralAccentColor,
    LiteralVariant,
    RadixThemesComponent,
)
from .base import (
    LiteralTextSize,
    LiteralTextWeight,
)


class Code(el.Code, RadixThemesComponent):
    """A block level extended quotation."""

    tag = "Code"

    # The visual variant to apply: "solid" | "soft" | "outline" | "ghost"
    variant: Optional[Var[LiteralVariant]] = None

    # Text size: "1" - "9"
    size: Optional[Var[LiteralTextSize]] = None

    # Thickness of text: "light" | "regular" | "medium" | "bold"
    weight: Optional[Var[LiteralTextWeight]] = None

    # Overrides the accent color inherited from the Theme.
    color_scheme: Optional[Var[LiteralAccentColor]] = None

    # Whether to render the text with higher contrast color
    high_contrast: Optional[Var[bool]] = None
