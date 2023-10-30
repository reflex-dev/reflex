"""Components for rendering text.

https://www.radix-ui.com/themes/docs/theme/typography
"""
from __future__ import annotations

from typing import Literal

from reflex.vars import Var

from .base import (
    CommonMarginProps,
    LiteralAccentColor,
    LiteralVariant,
    RadixThemesComponent,
)

LiteralTextWeight = Literal["light", "regular", "medium", "bold"]
LiteralTextAlign = Literal["left", "center", "right"]
LiteralTextSize = Literal["1", "2", "3", "4", "5", "6", "7", "8", "9"]
LiteralTextTrim = Literal["normal", "start", "end", "both"]


class Text(CommonMarginProps, RadixThemesComponent):
    """A foundational text primitive based on the <span> element."""

    tag = "Text"

    # Change the default rendered element for the one passed as a child, merging their props and behavior.
    as_child: Var[bool]

    # Change the default rendered element into a semantically appropriate alternative (cannot be used with asChild)
    as_: Var[str]

    # Text size: "1" - "9"
    size: Var[LiteralTextSize]

    # Thickness of text: "light" | "regular" | "medium" | "bold"
    weight: Var[LiteralTextWeight]

    # Alignment of text in element: "left" | "center" | "right"
    align: Var[LiteralTextAlign]

    # Removes the leading trim space: "normal" | "start" | "end" | "both"
    trim: Var[LiteralTextTrim]

    # Overrides the accent color inherited from the Theme.
    color: Var[LiteralAccentColor]

    # Whether to render the text with higher contrast color
    high_contrast: Var[bool]


class Heading(Text):
    """A semantic heading element."""

    tag = "Heading"


class Blockquote(CommonMarginProps, RadixThemesComponent):
    """A block level extended quotation."""

    tag = "Blockquote"

    # Text size: "1" - "9"
    size: Var[LiteralTextSize]

    # Thickness of text: "light" | "regular" | "medium" | "bold"
    weight: Var[LiteralTextWeight]

    # Overrides the accent color inherited from the Theme.
    color: Var[LiteralAccentColor]

    # Whether to render the text with higher contrast color
    high_contrast: Var[bool]


class Code(Blockquote):
    """Marks text to signify a short fragment of computer code."""

    tag = "Code"

    # The visual variant to apply: "solid" | "soft" | "outline" | "ghost"
    variant: Var[LiteralVariant]


class Em(CommonMarginProps, RadixThemesComponent):
    """Marks text to stress emphasis."""

    tag = "Em"


class Kbd(CommonMarginProps, RadixThemesComponent):
    """Represents keyboard input or a hotkey."""

    tag = "Kbd"

    # Text size: "1" - "9"
    size: Var[LiteralTextSize]


LiteralLinkUnderline = Literal["auto", "hover", "always"]


class Link(CommonMarginProps, RadixThemesComponent):
    """A semantic element for navigation between pages."""

    tag = "Link"

    # Change the default rendered element for the one passed as a child, merging their props and behavior.
    as_child: Var[bool]

    # Text size: "1" - "9"
    size: Var[LiteralTextSize]

    # Thickness of text: "light" | "regular" | "medium" | "bold"
    weight: Var[LiteralTextWeight]

    # Removes the leading trim space: "normal" | "start" | "end" | "both"
    trim: Var[LiteralTextTrim]

    # Sets the visibility of the underline affordance: "auto" | "hover" | "always"
    underline: Var[LiteralLinkUnderline]

    # Overrides the accent color inherited from the Theme.
    color: Var[LiteralAccentColor]

    # Whether to render the text with higher contrast color
    high_contrast: Var[bool]


class Quote(CommonMarginProps, RadixThemesComponent):
    """A short inline quotation."""

    tag = "Quote"


class Strong(CommonMarginProps, RadixThemesComponent):
    """Marks text to signify strong importance."""

    tag = "Strong"
