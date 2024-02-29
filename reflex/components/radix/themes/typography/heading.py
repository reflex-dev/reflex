"""Components for rendering heading.

https://www.radix-ui.com/themes/docs/theme/typography
"""
from __future__ import annotations

from reflex import el
from reflex.vars import Var
from typing import Optional

from ..base import (
    LiteralAccentColor,
    RadixThemesComponent,
)
from .base import (
    LiteralTextAlign,
    LiteralTextSize,
    LiteralTextTrim,
    LiteralTextWeight,
)


class Heading(el.H1, RadixThemesComponent):
    """A foundational text primitive based on the <span> element."""

    tag = "Heading"

    # Change the default rendered element for the one passed as a child, merging their props and behavior.
    as_child: Optional[Var[bool]] = None

    # Change the default rendered element into a semantically appropriate alternative (cannot be used with asChild)
    as_: Optional[Var[str]] = None

    # Text size: "1" - "9"
    size: Optional[Var[LiteralTextSize]] = None

    # Thickness of text: "light" | "regular" | "medium" | "bold"
    weight: Optional[Var[LiteralTextWeight]] = None

    # Alignment of text in element: "left" | "center" | "right"
    align: Optional[Var[LiteralTextAlign]] = None

    # Removes the leading trim space: "normal" | "start" | "end" | "both"
    trim: Optional[Var[LiteralTextTrim]] = None

    # Overrides the accent color inherited from the Theme.
    color_scheme: Optional[Var[LiteralAccentColor]] = None

    # Whether to render the text with higher contrast color
    high_contrast: Optional[Var[bool]] = None
