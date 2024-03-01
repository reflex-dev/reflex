"""Components for rendering text.
from typing import Optional
https://www.radix-ui.com/themes/docs/theme/typography.
"""
from __future__ import annotations

from typing import Literal, Optional

from reflex import el
from reflex.components.component import ComponentNamespace
from reflex.vars import Var

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

LiteralType = Literal[
    "p",
    "label",
    "div",
    "span",
    "b",
    "i",
    "u",
    "abbr",
    "cite",
    "del",
    "em",
    "ins",
    "kbd",
    "mark",
    "s",
    "samp",
    "sub",
    "sup",
]


class Text(el.Span, RadixThemesComponent):
    """A foundational text primitive based on the <span> element."""

    tag: str = "Text"

    # Change the default rendered element for the one passed as a child, merging their props and behavior.
    as_child: Optional[Var[bool]] = None

    # Change the default rendered element into a semantically appropriate alternative (cannot be used with asChild)
    as_: Var[LiteralType] = "p"  # type: ignore

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


class Span(Text):
    """A variant of text rendering as <span> element."""

    as_: Var[LiteralType] = "span"  # type: ignore


class Em(el.Em, RadixThemesComponent):
    """Marks text to stress emphasis."""

    tag: str = "Em"


class Kbd(el.Kbd, RadixThemesComponent):
    """Represents keyboard input or a hotkey."""

    tag: str = "Kbd"

    # Text size: "1" - "9"
    size: Optional[Var[LiteralTextSize]] = None


class Quote(el.Q, RadixThemesComponent):
    """A short inline quotation."""

    tag: str = "Quote"


class Strong(el.Strong, RadixThemesComponent):
    """Marks text to signify strong importance."""

    tag: str = "Strong"


class TextNamespace(ComponentNamespace):
    """Checkbox components namespace."""

    __call__ = staticmethod(Text.create)
    em = staticmethod(Em.create)
    kbd = staticmethod(Kbd.create)
    quote = staticmethod(Quote.create)
    strong = staticmethod(Strong.create)
    span = staticmethod(Span.create)


text = TextNamespace()
