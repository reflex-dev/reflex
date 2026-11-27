"""Text, and the inline elements that mark it up."""

from __future__ import annotations

from typing import ClassVar, Literal

from reflex_base.components.component import ComponentNamespace, field
from reflex_base.vars.base import Var
from reflex_components_core.core.breakpoints import Responsive
from reflex_components_core.core.markdown_component_map import MarkdownComponentMap
from reflex_components_core.el import elements

from reflex_components_ui.base import UIComponent
from reflex_components_ui.style import ComponentStyles
from reflex_components_ui.styles.text import EM, KBD, QUOTE, STRONG, TEXT
from reflex_components_ui.themes import LiteralAccentColor
from reflex_components_ui.typography.base import (
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


class Text(UIComponent, elements.Span, MarkdownComponentMap):
    """A foundational text primitive based on the <span> element."""

    tag = "span"

    styles: ClassVar[ComponentStyles] = TEXT

    _as_tags: ClassVar[frozenset[str]] = frozenset(("span", "div", "label", "p"))

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


class Em(UIComponent, elements.Em):
    """Marks text to stress emphasis."""

    tag = "em"

    styles: ClassVar[ComponentStyles] = EM


class Kbd(UIComponent, elements.Kbd):
    """Represents keyboard input or a hotkey."""

    tag = "kbd"

    styles: ClassVar[ComponentStyles] = KBD

    size: Var[LiteralTextSize] = field(doc='Text size: "1" - "9"')


class Quote(UIComponent, elements.Q):
    """A short inline quotation."""

    tag = "q"

    styles: ClassVar[ComponentStyles] = QUOTE


class Strong(UIComponent, elements.Strong):
    """Marks text to signify strong importance."""

    tag = "strong"

    styles: ClassVar[ComponentStyles] = STRONG


class TextNamespace(ComponentNamespace):
    """Text and the inline elements that mark it up."""

    __call__ = staticmethod(Text.create)
    em = staticmethod(Em.create)
    kbd = staticmethod(Kbd.create)
    quote = staticmethod(Quote.create)
    strong = staticmethod(Strong.create)
    span = staticmethod(Span.create)


text = TextNamespace()
