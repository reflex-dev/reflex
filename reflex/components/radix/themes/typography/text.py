"""Components for rendering text.

https://www.radix-ui.com/themes/docs/theme/typography
"""

from __future__ import annotations

from typing import Literal

from reflex.components.component import ComponentNamespace
from reflex.components.core.breakpoints import Responsive
from reflex.components.el import elements
from reflex.ivars.base import ImmutableVar

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


class Text(elements.Span, RadixThemesComponent):
    """A foundational text primitive based on the <span> element."""

    tag = "Text"

    # Change the default rendered element for the one passed as a child, merging their props and behavior.
    as_child: ImmutableVar[bool]

    # Change the default rendered element into a semantically appropriate alternative (cannot be used with asChild)
    as_: ImmutableVar[LiteralType] = "p"  # type: ignore

    # Text size: "1" - "9"
    size: ImmutableVar[Responsive[LiteralTextSize]]

    # Thickness of text: "light" | "regular" | "medium" | "bold"
    weight: ImmutableVar[Responsive[LiteralTextWeight]]

    # Alignment of text in element: "left" | "center" | "right"
    align: ImmutableVar[Responsive[LiteralTextAlign]]

    # Removes the leading trim space: "normal" | "start" | "end" | "both"
    trim: ImmutableVar[Responsive[LiteralTextTrim]]

    # Overrides the accent color inherited from the Theme.
    color_scheme: ImmutableVar[LiteralAccentColor]

    # Whether to render the text with higher contrast color
    high_contrast: ImmutableVar[bool]


class Span(Text):
    """A variant of text rendering as <span> element."""

    as_: ImmutableVar[LiteralType] = "span"  # type: ignore


class Em(elements.Em, RadixThemesComponent):
    """Marks text to stress emphasis."""

    tag = "Em"


class Kbd(elements.Kbd, RadixThemesComponent):
    """Represents keyboard input or a hotkey."""

    tag = "Kbd"

    # Text size: "1" - "9"
    size: ImmutableVar[LiteralTextSize]


class Quote(elements.Q, RadixThemesComponent):
    """A short inline quotation."""

    tag = "Quote"


class Strong(elements.Strong, RadixThemesComponent):
    """Marks text to signify strong importance."""

    tag = "Strong"


class TextNamespace(ComponentNamespace):
    """Checkbox components namespace."""

    __call__ = staticmethod(Text.create)
    em = staticmethod(Em.create)
    kbd = staticmethod(Kbd.create)
    quote = staticmethod(Quote.create)
    strong = staticmethod(Strong.create)
    span = staticmethod(Span.create)


text = TextNamespace()
