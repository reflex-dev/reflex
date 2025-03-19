"""Metadata classes."""

from reflex.components.el.element import Element
from reflex.components.el.elements.inline import ReferrerPolicy
from reflex.components.el.elements.media import CrossOrigin
from reflex.vars.base import Var

from .base import BaseHTML


class Base(BaseHTML):
    """Display the base element."""

    tag = "base"

    tag = "base"
    href: Var[str]
    target: Var[str]


class Head(BaseHTML):
    """Display the head element."""

    tag = "head"


class Link(BaseHTML):
    """Display the link element."""

    tag = "link"

    # Specifies the CORS settings for the linked resource
    cross_origin: Var[CrossOrigin]

    # Specifies the URL of the linked document/resource
    href: Var[str]

    # Specifies the language of the text in the linked document
    href_lang: Var[str]

    # Allows a browser to check the fetched link for integrity
    integrity: Var[str]

    # Specifies on what device the linked document will be displayed
    media: Var[str]

    # Specifies the referrer policy of the linked document
    referrer_policy: Var[ReferrerPolicy]

    # Specifies the relationship between the current document and the linked one
    rel: Var[str]

    # Specifies the sizes of icons for visual media
    sizes: Var[str]

    # Specifies the MIME type of the linked document
    type: Var[str]


class Meta(BaseHTML):  # Inherits common attributes from BaseHTML
    """Display the meta element."""

    tag = "meta"  # The HTML tag for this element is <meta>

    # Specifies the character encoding for the HTML document
    char_set: Var[str]

    # Defines the content of the metadata
    content: Var[str]

    # Provides an HTTP header for the information/value of the content attribute
    http_equiv: Var[str]

    # Specifies a name for the metadata
    name: Var[str]


class Title(Element):
    """Display the title element."""

    tag = "title"


# Had to be named with an underscore so it doesn't conflict with reflex.style Style in pyi
class StyleEl(Element):
    """Display the style element."""

    tag = "style"

    media: Var[str]

    special_props: list[Var] = [Var(_js_expr="suppressHydrationWarning")]


base = Base.create
head = Head.create
link = Link.create
meta = Meta.create
title = Title.create
style = StyleEl.create
