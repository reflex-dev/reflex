"""Metadata classes."""

from reflex_base.components.component import field
from reflex_base.vars.base import Var

from reflex_components_core.el.element import Element
from reflex_components_core.el.elements.inline import ReferrerPolicy
from reflex_components_core.el.elements.media import CrossOrigin

from .base import BaseHTML


class Base(BaseHTML):
    """Display the base element."""

    tag = "base"

    href: Var[str]
    target: Var[str]


class Head(BaseHTML):
    """Display the head element."""

    tag = "head"


class Link(BaseHTML):
    """Display the link element."""

    tag = "link"

    cross_origin: Var[CrossOrigin] = field(
        doc="Specifies the CORS settings for the linked resource"
    )

    href: Var[str] = field(doc="Specifies the URL of the linked document/resource")

    href_lang: Var[str] = field(
        doc="Specifies the language of the text in the linked document"
    )

    integrity: Var[str] = field(
        doc="Allows a browser to check the fetched link for integrity"
    )

    media: Var[str] = field(
        doc="Specifies on what device the linked document will be displayed"
    )

    referrer_policy: Var[ReferrerPolicy] = field(
        doc="Specifies the referrer policy of the linked document"
    )

    rel: Var[str] = field(
        doc="Specifies the relationship between the current document and the linked one"
    )

    sizes: Var[str] = field(doc="Specifies the sizes of icons for visual media")

    type: Var[str] = field(doc="Specifies the MIME type of the linked document")


class Meta(BaseHTML):  # Inherits common attributes from BaseHTML
    """Display the meta element."""

    tag = "meta"  # The HTML tag for this element is <meta>

    char_set: Var[str] = field(
        doc="Specifies the character encoding for the HTML document"
    )

    content: Var[str] = field(doc="Defines the content of the metadata")

    http_equiv: Var[str] = field(
        doc="Provides an HTTP header for the information/value of the content attribute"
    )

    name: Var[str] = field(doc="Specifies a name for the metadata")

    property: Var[str] = field(doc="The type of metadata value.")


class Title(Element):
    """Display the title element."""

    tag = "title"


# Had to be named with an underscore so it doesn't conflict with reflex.style Style in pyi
class StyleEl(Element):
    """Display the style element."""

    tag = "style"

    media: Var[str]

    suppress_hydration_warning: Var[bool] = Var.create(True)


base = Base.create
head = Head.create
link = Link.create
meta = Meta.create
title = Title.create
style = StyleEl.create
