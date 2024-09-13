"""Element classes. This is an auto-generated file. Do not edit. See ../generate.py."""

from typing import List, Union

from reflex.components.el.element import Element
from reflex.vars.base import Var

from .base import BaseHTML


class Base(BaseHTML):  # noqa: E742
    """Display the base element."""

    tag = "base"

    tag = "base"
    href: Var[Union[str, int, bool]]
    target: Var[Union[str, int, bool]]


class Head(BaseHTML):  # noqa: E742
    """Display the head element."""

    tag = "head"


class Link(BaseHTML):  # noqa: E742
    """Display the link element."""

    tag = "link"

    # Specifies the CORS settings for the linked resource
    cross_origin: Var[Union[str, int, bool]]

    # Specifies the URL of the linked document/resource
    href: Var[Union[str, int, bool]]

    # Specifies the language of the text in the linked document
    href_lang: Var[Union[str, int, bool]]

    # Allows a browser to check the fetched link for integrity
    integrity: Var[Union[str, int, bool]]

    # Specifies on what device the linked document will be displayed
    media: Var[Union[str, int, bool]]

    # Specifies the referrer policy of the linked document
    referrer_policy: Var[Union[str, int, bool]]

    # Specifies the relationship between the current document and the linked one
    rel: Var[Union[str, int, bool]]

    # Specifies the sizes of icons for visual media
    sizes: Var[Union[str, int, bool]]

    # Specifies the MIME type of the linked document
    type: Var[Union[str, int, bool]]


class Meta(BaseHTML):  # Inherits common attributes from BaseHTML
    """Display the meta element."""

    tag = "meta"  # The HTML tag for this element is <meta>

    # Specifies the character encoding for the HTML document
    char_set: Var[Union[str, int, bool]]

    # Defines the content of the metadata
    content: Var[Union[str, int, bool]]

    # Provides an HTTP header for the information/value of the content attribute
    http_equiv: Var[Union[str, int, bool]]

    # Specifies a name for the metadata
    name: Var[Union[str, int, bool]]


class Title(Element):  # noqa: E742
    """Display the title element."""

    tag = "title"


# Had to be named with an underscore so it doesnt conflict with reflex.style Style in pyi
class StyleEl(Element):  # noqa: E742
    """Display the style element."""

    tag = "style"

    media: Var[Union[str, int, bool]]

    special_props: List[Var] = [Var(_js_expr="suppressHydrationWarning")]


base = Base.create
head = Head.create
link = Link.create
meta = Meta.create
title = Title.create
style = StyleEl.create
