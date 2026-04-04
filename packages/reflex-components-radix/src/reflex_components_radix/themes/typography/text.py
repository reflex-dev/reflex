"""Components for rendering text.

https://www.radix-ui.com/themes/docs/theme/typography
"""

from __future__ import annotations

from typing import Literal

from reflex_base.components.component import ComponentNamespace, field
from reflex_base.vars.base import Var
from reflex_components_core.core.breakpoints import Responsive
from reflex_components_core.core.markdown_component_map import MarkdownComponentMap
from reflex_components_core.el import elements

from reflex_components_radix.themes.base import LiteralAccentColor, RadixThemesComponent

from .base import LiteralTextAlign, LiteralTextSize, LiteralTextTrim, LiteralTextWeight

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


class Text(elements.Span, RadixThemesComponent, MarkdownComponentMap):
    """A foundational text primitive based on the <span> element."""

    tag = "Text"

    as_child: Var[bool] = field(
        doc="Change the default rendered element for the one passed as a child, merging their props and behavior."
    )

    as_: Var[LiteralType] = field(
        default=Var.create("p"),
        doc="Change the default rendered element into a semantically appropriate alternative (cannot be used with asChild)",
    )

    size: Var[Responsive[LiteralTextSize]] = field(doc='Text size: "1" - "9"')

    weight: Var[Responsive[LiteralTextWeight]] = field(
        doc='Thickness of text: "light" | "regular" | "medium" | "bold"'
    )

    align: Var[Responsive[LiteralTextAlign]] = field(
        doc='Alignment of text in element: "left" | "center" | "right"'
    )

    trim: Var[Responsive[LiteralTextTrim]] = field(
        doc='Removes the leading trim space: "normal" | "start" | "end" | "both"'
    )

    color_scheme: Var[LiteralAccentColor] = field(
        doc="Overrides the accent color inherited from the Theme."
    )

    high_contrast: Var[bool] = field(
        doc="Whether to render the text with higher contrast color"
    )


class Span(Text):
    """A variant of text rendering as <span> element."""

    as_: Var[LiteralType] = Var.create("span")


class Em(elements.Em, RadixThemesComponent):
    """Marks text to stress emphasis."""

    tag = "Em"


class Kbd(elements.Kbd, RadixThemesComponent):
    """Represents keyboard input or a hotkey."""

    tag = "Kbd"

    size: Var[LiteralTextSize] = field(doc='Text size: "1" - "9"')


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
